import os
import discord
from discord import app_commands
from discord.ext import commands, tasks

# آي دي السيرفر الخاص بك لتظهر الأوامر فوراً فيه
YOUR_GUILD_ID = 1497511041813450902

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # بدء مهمة فحص البوسترز التلقائية
        check_boosters.start()

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        try:
            # ربط الأوامر بسيرفرك الخاص مباشرة لتعمل فوراً
            guild = discord.Object(id=YOUR_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s) instantly to guild {YOUR_GUILD_ID}")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

bot = MyBot()

# قاعدة بيانات وهمية في الذاكرة للرولات المخصصة فقط
booster_roles = {}

# دالة مساعدة مطورة للتأكد من أن الشخص بوستر (تبحث عن رتبة البوست بأي اسم)
def is_booster(interaction: discord.Interaction) -> bool:
    member = interaction.user
    for role in member.roles:
        if "booster" in role.name.lower() or "boost" in role.name.lower() or role.is_premium_subscriber():
            return True
    return False

# --- 1. أمر إنشاء الرول (تم تعديله ليكون مخفياً ويرفع الرتبة تلقائياً) ---
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
    # تأجيل الرد وجعل العملية مخفية بالكامل (لا أحد يرى الرسائل غير المستخدم)
    await interaction.response.defer(ephemeral=True)

    # إنشاء الرول
    new_role = await guild.create_role(name=role_name, reason=f"Booster custom role for {member.name}")
    
    # جلب رتبة البوت لرفع الرتبة الجديدة تحتها مباشرة
    bot_member = guild.get_member(bot.user.id)
    bot_top_role = bot_member.top_role
    try:
        # رفع الرتبة الجديدة لتكون تحت أعلى رتبة للبوت بمرتبة واحدة
        await new_role.edit(position=bot_top_role.position - 1)
    except discord.Forbidden:
        print("تنبيه: البوت لم يستطع رفع الرتبة تلقائياً. يرجى سحب رتبة البوت في إعدادات السيرفر لأعلى القائمة.")
    except Exception as e:
        print(f"Error setting role position: {e}")

    # إعطاء الرول لصاحبه
    await member.add_roles(new_role)
    
    # حفظ الرول المخصص في الذاكرة
    booster_roles[member.id] = {
        "role_id": new_role.id,
        "shared_with": []
    }
    
    # الرد يظهر فقط للشخص ومخفي عن باقي السيرفر
    await interaction.followup.send(f"تم إنشاء رولك الخاص بنجاح وتم وضعه في الترتيب الصحيح تحت البوت!", ephemeral=True)

# --- 2. أمر تعديل الاسم واللون ---
@bot.tree.command(name="edit_role", description="تعديل اسم أو لون رولك الخاص")
@app_commands.choices(option=[
    app_commands.Choice(name="تغيير الاسم", value="name"),
    app_commands.Choice(name="تغيير اللون", value="color")
])
@app_commands.describe(option="اختر ماذا تريد أن تعدل", value="الاسم الجديد أو كود اللون الهكس (مثال: #ff0000)")
async def edit_role(interaction: discord.Interaction, option: app_commands.Choice[str], value: str):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتعديله.", ephemeral=True)
        return
    
    role_info = booster_roles[member.id]
    role = interaction.guild.get_role(role_info["role_id"])
    
    if not role:
        await interaction.response.send_message("لم يتم العثور على الرول الخاص بك في السيرفر.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if option.value == "name":
        await role.edit(name=value)
        await interaction.followup.send(f"تم تغيير اسم الرول إلى: **{value}**", ephemeral=True)
        
    elif option.value == "color":
        try:
            hex_color = value.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            discord_color = discord.Color.from_rgb(*rgb)
            await role.edit(color=discord_color)
            await interaction.followup.send("تم تغيير لون الرول بنجاح!", ephemeral=True)
        except Exception:
            await interaction.followup.send("صيغة اللون غير صحيحة. يرجى استخدام صيغة Hex مثل: `#ff0000`", ephemeral=True)

# --- 3. أمر تعديل الأيقونة بالرفع المباشر ---
@bot.tree.command(name="edit_role_icon", description="تغيير أيقونة رولك المخصص عن طريق رفع صورة")
@app_commands.describe(image="ارفع الصورة التي تريدها كأيقونة للرول")
async def edit_role_icon(interaction: discord.Interaction, image: discord.Attachment):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتعديله.", ephemeral=True)
        return
    
    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.response.send_message("يرجى رفع ملف صوري فقط (PNG, JPG, Gif).", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    
    role_info = booster_roles[member.id]
    role = interaction.guild.get_role(role_info["role_id"])
    
    if not role:
        await interaction.followup.send("لم يتم العثور على الرول الخاص بك.", ephemeral=True)
        return

    icon_bytes = await image.read()
    try:
        await role.edit(display_icon=icon_bytes)
        await interaction.followup.send("تم تغيير أيقونة الرول بنجاح!", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("لا يمكنني تعديل الأيقونة. تأكد من أن السيرفر يمتلك ليفل البوست المطلوب لهذه الميزة (ليفل 2+).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"حدث خطأ أثناء تعديل الأيقونة: {e}", ephemeral=True)

# --- 4. أمر مشاركة الرول مع 3 أشخاص كحد أقصى ---
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
        await interaction.followup.send("حدث خطأ، لم يتم العثور على الرول الخاص بك.", ephemeral=True)

# --- 5. فحص البوسترز التلقائي كل 10 دقائق وحذف الرتب ---
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
                        print(f"تم حذف الرول المخصص {info['role_id']} لانتهاء البوست.")
                    except Exception as e:
                        print(f"خطأ أثناء حذف الرول: {e}")
                
                booster_roles.pop(booster_id, None)

# تشغيل البوت عبر التوكن من Railway
token = os.getenv("DISCORD_TOKEN")
bot.run(token)
