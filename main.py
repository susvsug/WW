import os
import discord
from discord import app_commands
from discord.ext import commands, tasks

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        check_boosters.start()

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        try:
            # مزامنة تلقائية لجميع السيرفرات دون الحاجة لـ ID
            for guild in self.guilds:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"✅ Synced {len(synced)} commands successfully to: {guild.name} ({guild.id})")
        except Exception as e:
            print(f"❌ Failed to sync: {e}")

bot = MyBot()

# قاعدة بيانات وهمية في الذاكرة للرولات المخصصة
booster_roles = {}

# دالة مساعدة للتأكد من أن الشخص بوستر
def is_booster(interaction: discord.Interaction) -> bool:
    member = interaction.user
    for role in member.roles:
        if "booster" in role.name.lower() or "boost" in role.name.lower() or role.is_premium_subscriber():
            return True
    return False

# --- 1. أمر إنشاء الرول (فوق رتبة البوستر مباشرة) ---
@bot.tree.command(name="create_role", description="أنشئ رولك الخاص لأنك بوستر!")
@app_commands.describe(role_name="اسم الرول الجديد الخاص بك")
async def create_role(interaction: discord.Interaction, role_name: str):
    if not is_booster(interaction):
        await interaction.response.send_message("عذراً، هذا الأمر مخصص لداعمي السيرفر (Server Booster) فقط!", ephemeral=True)
        return

    member = interaction.user
    if member.id in booster_roles:
        await interaction.response.send_message("لديك رول خاص بك بالفعل!", ephemeral=True)
        return

    guild = interaction.guild
    await interaction.response.defer(ephemeral=True)

    try:
        new_role = await guild.create_role(name=role_name, reason=f"Booster custom role for {member.name}")
    except Exception as e:
        await interaction.followup.send("فشل إنشاء الرول. تأكد من إعطاء البوت صلاحية Manage Roles.", ephemeral=True)
        return

    # إعطاء الرول للعضو
    await member.add_roles(new_role)

    # البحث عن رتبة البوستر الأساسية بالسيرفر لرفع الرول فوقها
    booster_role = None
    for r in guild.roles:
        if r.is_premium_subscriber():
            booster_role = r
            break

    if not booster_role:
        for r in guild.roles:
            if "booster" in r.name.lower() or "boost" in r.name.lower() or "داعم" in r.name:
                booster_role = r
                break

    try:
        bot_member = guild.get_member(bot.user.id)
        if booster_role:
            target_position = booster_role.position + 1
            # حماية لكي لا يتعدى الرول رتبة البوت نفسه
            if target_position >= bot_member.top_role.position:
                target_position = max(1, bot_member.top_role.position - 1)
                
            await new_role.edit(position=target_position)
            print(f"Moved role above booster role to position {target_position}")
        else:
            target_position = max(1, bot_member.top_role.position - 1)
            await new_role.edit(position=target_position)
    except Exception as e:
        print(f"Failed to move role position: {e}")

    booster_roles[member.id] = {
        "role_id": new_role.id,
        "shared_with": []
    }
    await interaction.followup.send(f"تم إنشاء رولك الخاص بنجاح ووضعه فوق رتبة البوستر! 🎉", ephemeral=True)

# --- 2. أمر حذف الرول الخاص (المطلوب ⚠️) ---
@bot.tree.command(name="delete_role", description="حذف رولك الخاص نهائياً من السيرفر")
async def delete_role(interaction: discord.Interaction):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رولاً مخصصاً لتقوم بحذفه.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    role_info = booster_roles[member.id]
    role = interaction.guild.get_role(role_info["role_id"])
    
    if role:
        try:
            await role.delete(reason="حذف بطلب من صاحب الرتبة")
            await interaction.followup.send("تم حذف رولك المخصص بنجاح من السيرفر!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"فشل حذف الرتبة من السيرفر: {e}", ephemeral=True)
    else:
        await interaction.followup.send("لم يُعثر على الرول في قائمة رتب السيرفر (قد يكون حُذف يدوياً).", ephemeral=True)
        
    # إزالة السجل من ذاكرة البوت في كل الحالات
    booster_roles.pop(member.id, None)

# --- 3. أمر تعديل الاسم ---
@bot.tree.command(name="edit_name", description="تغيير اسم رولك الخاص")
@app_commands.describe(new_name="الاسم الجديد للرول")
async def edit_name(interaction: discord.Interaction, new_name: str):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتعديله.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    role_info = booster_roles[member.id]
    role = interaction.guild.get_role(role_info["role_id"])
    
    if role:
        await role.edit(name=new_name)
        await interaction.followup.send(f"تم تغيير اسم الرول إلى: **{new_name}**", ephemeral=True)
    else:
        await interaction.followup.send("لم يتم العثور على الرول الخاص بك.", ephemeral=True)

# --- 4. أمر تغيير اللون ---
@bot.tree.command(name="edit_color", description="تغيير لون رولك الخاص باستخدام كود هيكس (Hex Color)")
@app_commands.describe(hex_code="كود اللون الهكس (مثال: #ff0000 للون الأحمر)")
async def edit_color(interaction: discord.Interaction, hex_code: str):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتعديله.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    role_info = booster_roles[member.id]
    role = interaction.guild.get_role(role_info["role_id"])
    
    if role:
        try:
            clean_hex = hex_code.lstrip('#')
            rgb = tuple(int(clean_hex[i:i+2], 16) for i in (0, 2, 4))
            discord_color = discord.Color.from_rgb(*rgb)
            await role.edit(color=discord_color)
            await interaction.followup.send("تم تغيير لون الرول بنجاح!", ephemeral=True)
        except Exception:
            await interaction.followup.send("صيغة اللون غير صحيحة. يرجى استخدام صيغة Hex مثل: `#ff0000`", ephemeral=True)
    else:
        await interaction.followup.send("لم يتم العثور على الرول الخاص بك.", ephemeral=True)

# --- 5. أمر تعديل الأيقونة ---
@bot.tree.command(name="edit_icon", description="تغيير أيقونة رولك المخصص عن طريق رفع صورة")
@app_commands.describe(image="ارفع الصورة التي تريد استخدامها كأيقونة للرول (PNG أو JPG)")
async def edit_icon(interaction: discord.Interaction, image: discord.Attachment):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتعديله.", ephemeral=True)
        return
    
    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.response.send_message("يرجى رفع ملف صوري فقط (PNG, JPG, JPEG).", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    role_info = booster_roles[member.id]
    role = interaction.guild.get_role(role_info["role_id"])
    
    if not role:
        await interaction.followup.send("لم يتم العثور على الرول الخاص بك.", ephemeral=True)
        return

    try:
        icon_bytes = await image.read()
        await role.edit(display_icon=icon_bytes)
        await interaction.followup.send("تم تعيين أيقونة الرول الخاصة بك بنجاح! 🎉", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("فشل تعديل الأيقونة. تأكد من إعطاء البوت صلاحية إدارة الرتب ورفع ترتيب رتبته.", ephemeral=True)
    except discord.HTTPException as e:
        if e.code == 50035:
            await interaction.followup.send("عذراً، ميزة أيقونات الرتب تتطلب أن يكون السيرفر حاصلاً على Boost Level 2 في ديسكورد.", ephemeral=True)
        else:
            await interaction.followup.send(f"حدث خطأ من طرف ديسكورد أثناء تعديل الأيقونة: {e}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"حدث خطأ غير متوقع: {e}", ephemeral=True)

# --- 6. أمر مشاركة الرول مع صديق ---
@bot.tree.command(name="share_role", description="شارك رولك المخصص مع صديق (الحد الأقصى 3 أشخاص)")
@app_commands.describe(target_member="الشخص الذي تريد إعطائه رولك")
async def share_role(interaction: discord.Interaction, target_member: discord.Member):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتشاركه.", ephemeral=True)
        return
    
    role_info = booster_roles[member.id]
    if len(role_info["shared_with"]) >= 3:
        await interaction.response.send_message("لقد وصلت للحد الأقصى لمشاركة الرول (3 أشخاص فقط).", ephemeral=True)
        return
    if target_member.id in role_info["shared_with"] or target_member.id == member.id:
        await interaction.response.send_message("هذا الشخص لديه الرول بالفعل.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    role = interaction.guild.get_role(role_info["role_id"])
    
    if role:
        await target_member.add_roles(role)
        role_info["shared_with"].append(target_member.id)
        await interaction.followup.send(f"تم إعطاء الرول الخاص بك للعضو {target_member.mention} بنجاح!", ephemeral=True)
    else:
        await interaction.followup.send("لم يتم العثور على الرول الخاص بك.", ephemeral=True)

# --- 7. أمر حذف صديق من الرول ---
@bot.tree.command(name="remove_member", description="إزالة صديق من رولك الخاص وسحب الرتبة منه")
@app_commands.describe(target_member="العضو المراد إزالته وسحب رولك منه")
async def remove_member(interaction: discord.Interaction, target_member: discord.Member):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتعديله.", ephemeral=True)
        return
        
    role_info = booster_roles[member.id]
    if target_member.id not in role_info["shared_with"]:
        await interaction.response.send_message("هذا الشخص ليس مضافاً لرولك الخاص.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    role = interaction.guild.get_role(role_info["role_id"])
    
    if role:
        try:
            await target_member.remove_roles(role)
            role_info["shared_with"].remove(target_member.id)
            await interaction.followup.send(f"تم سحب الرول من العضو {target_member.mention} بنجاح!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"حدث خطأ أثناء إزالة الرول: {e}", ephemeral=True)
    else:
        await interaction.followup.send("لم يتم العثور على الرتبة المخصصة الخاصة بك.", ephemeral=True)

# --- 8. فحص البوسترز التلقائي ---
@tasks.loop(minutes=10)
async def check_boosters():
    for guild in bot.guilds:
        for booster_id, info in list(booster_roles.items()):
            member = guild.get_member(booster_id)
            is_still_boosting = False
            if member:
                for role in member.roles:
                    if "booster" in role.name.lower() or "boost" in role.name.lower() or role.is_premium_subscriber():
                        is_still_boosting = True
                        break
            if not is_still_boosting:
                role = guild.get_role(info["role_id"])
                if role:
                    try:
                        await role.delete(reason="انتهت مدة البوست الخاصة بالعضو.")
                    except Exception as e:
                        print(f"خطأ أثناء حذف الرول: {e}")
                booster_roles.pop(booster_id, None)

# تشغيل البوت عبر التوكن من Railway
token = os.getenv("DISCORD_TOKEN")
bot.run(token)
