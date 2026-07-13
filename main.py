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
        # تم وضع البريفكس العادي ليكون ! لأمر المزامنة السري
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

# --- أمر سري للمزامنة يدوياً بالرسائل العادية لتحديث كاش ديسكورد فوراً ---
# فقط اكتب في أي شات بالسيرفر: !sync
@bot.command(name="sync")
@commands.is_owner() # للتأكد من أن صاحب البوت فقط من يستطيع استخدامه
async def sync_commands(ctx):
    try:
        guild = discord.Object(id=YOUR_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        await ctx.send(f"✅ تم إجبار ديسكورد على مزامنة {len(synced)} أمر بنجاح! يرجى إغلاق تطبيق ديسكورد وفتحه الآن.")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ أثناء المزامنة: {e}")

# --- 1. أمر إنشاء الرول المتتالي تحت البوت تلقائياً وبصمت ---
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
    # تأجيل الرد وجعل العملية مخفية بالكامل (لا يرى الرسالة إلا منفذ الأمر)
    await interaction.response.defer(ephemeral=True)

    # إنشاء الرول
    try:
        new_role = await guild.create_role(name=role_name, reason=f"Booster custom role for {member.name}")
    except Exception as e:
        await interaction.followup.send("فشل إنشاء الرول. تأكد من إعطاء البوت صلاحية Manage Roles.", ephemeral=True)
        return

    # إعطاء الرول لصاحبه فوراً
    await member.add_roles(new_role)
    
    # جلب رتبة البوت لرفع الرتبة الجديدة تحتها مباشرة
    bot_member = guild.get_member(bot.user.id)
    bot_top_role = bot_member.top_role
    
    try:
        # نضع الرتبة الجديدة دائماً تحت رتبة البوت بمرتبة واحدة (Position - 1)
        await new_role.edit(position=max(1, bot_top_role.position - 1))
        print(f"تم إنشاء وترتيب رول بنجاح وتحت البوت مباشرة للعضو: {member.name}")
    except discord.Forbidden:
        print("تنبيه: البوت لم يستطع تغيير الترتيب. يرجى سحب رتبة البوت إلى أعلى القائمة في إعدادات السيرفر.")
    except Exception as e:
        print(f"Error setting role position: {e}")

    # حفظ الرول المخصص في الذاكرة للتحكم به لاحقاً وحذفه عند انتهاء البوست
    booster_roles[member.id] = {
        "role_id": new_role.id,
        "shared_with": []
    }
    
    # رسالة التأكيد تظهر للشخص فقط ومخفية عن باقي الأعضاء
    await interaction.followup.send(f"تم إنشاء رولك الخاص بنجاح وتم وضعه في الترتيب الصحيح تحت البوت!", ephemeral=True)

# --- 2. أمر تعديل الاسم واللون العادي ---
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
            await role.edit(color=discord_color, primary_color=None, secondary_color=None)
            await interaction.followup.send("تم تغيير لون الرول بنجاح!", ephemeral=True)
        except Exception:
            await interaction.followup.send("صيغة اللون غير صحيحة. يرجى استخدام صيغة Hex مثل: `#ff0000`", ephemeral=True)

# --- 3. أمر استخدام تدرجات الألوان الرسمية ثنائية اللون (Discord Role Gradients) ---
@bot.tree.command(name="gradient_role", description="اختر تدرجاً لونياً رسمياً (لونين معاً) لرولك الخاص!")
@app_commands.choices(gradient=[
    app_commands.Choice(name="Neon Sunset (وردي مشع + بنفسجي عميق)", value="#ff007f|#4b0082"),
    app_commands.Choice(name="Ocean Breeze (أزرق سماوي + نيلي غامق)", value="#00d2ff|#3a7bd5"),
    app_commands.Choice(name="Forest Emerald (أخضر ليموني + زمردي)", value="#a8ff78|#78ffd6"),
    app_commands.Choice(name="Cyber Gold (ذهبي دافئ + برتقالي ناري)", value="#f12711|#f5af19"),
    app_commands.Choice(name="Cotton Candy (وردي ناعم + أزرق فاتح)", value="#ff00cc|#333399")
])
async def gradient_role(interaction: discord.Interaction, gradient: app_commands.Choice[str]):
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
    
    # فصل اللونين عن بعضهما (Primary & Secondary)
    color1_hex, color2_hex = gradient.value.split('|')
    
    # تحويل الألوان إلى صيغة ديسكورد الرسمية
    rgb1 = tuple(int(color1_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    rgb2 = tuple(int(color2_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    primary_color = discord.Color.from_rgb(*rgb1)
    secondary_color = discord.Color.from_rgb(*rgb2)
    
    try:
        await role.edit(primary_color=primary_color, secondary_color=secondary_color)
        await interaction.followup.send(f"تم تطبيق التدرج اللوني الرسمي **{gradient.name}** بنجاح!", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("فشل تعديل الألوان. تأكد من رتبة البوت وصلاحياته في السيرفر.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("تأكد أن سيرفرك يمتلك ليفل البوست المطلوب لتفعيل ميزة التدرج اللوني للرتب.", ephemeral=True)

# --- 4. أمر حذف الرول الخاص بالكامل ---
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
            await role.delete(reason=f"تم الحذف بناءً على طلب العضو البوستر: {member.name}")
            await interaction.followup.send("تم حذف رولك المخصص بنجاح من السيرفر وقاعدة بيانات البوت!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"فشل حذف الرتبة من السيرفر: {e}", ephemeral=True)
    else:
        await interaction.followup.send("تمت إزالة السجل، لم يُعثر على الرول بالفعل في قائمة رتب السيرفر.", ephemeral=True)
        
    booster_roles.pop(member.id, None)

# --- 5. أمر تعديل الأيقونة بالرفع المباشر ---
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

# --- 6. أمر مشاركة الرول مع 3 أشخاص كحد أقصى ---
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

# --- 7. أمر حذف شخص من الرول وسحبه منه ---
@bot.tree.command(name="remove_shared_member", description="إزالة صديق من الأشخاص الثلاثة المشاركين لرولك وسحب الرتبة منه")
@app_commands.describe(target_member="العضو المراد إزالته وسحب رولك منه")
async def remove_shared_member(interaction: discord.Interaction, target_member: discord.Member):
    member = interaction.user
    if member.id not in booster_roles:
        await interaction.response.send_message("لا تملك رول خاص بالبوست لتعديل مشاركته.", ephemeral=True)
        return
        
    role_info = booster_roles[member.id]
    
    if target_member.id not in role_info["shared_with"]:
        await interaction.response.send_message("هذا الشخص غير مضاف إلى رولك المخصص أصلاً.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    role = interaction.guild.get_role(role_info["role_id"])
    
    if role:
        try:
            await target_member.remove_roles(role, reason=f"تمت إزالته من قبل صاحب الرول: {member.name}")
            role_info["shared_with"].remove(target_member.id)
            await interaction.followup.send(f"تم سحب رولك الخاص من العضو {target_member.mention} بنجاح وحذفه من قائمتك!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"حدث خطأ أثناء إزالة الرول من الشخص: {e}", ephemeral=True)
    else:
        await interaction.followup.send("لم يتم العثور على الرتبة المخصصة الخاصة بك في السيرفر.", ephemeral=True)

# --- 8. فحص البوسترز التلقائي كل 10 دقائق وحذف الرتب لمن انتهى البوست ---
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
