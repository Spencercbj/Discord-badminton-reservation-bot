import discord
from discord.ext import commands
import os
import re
import logging
import aiosqlite
from dotenv import load_dotenv
from discord.ui import Button, View, Select
from datetime import datetime

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

ADMIN_CHANNEL = 1474427765859287215
RESERVATION_CHANNEL = 1475537034318971032
ADMIN_ROLE_ID = 1474441478918115554
deadline = None
reservation = False
reservation_date = None
MAX_PLAYERS = 5


class MyBot(commands.Bot):
    def __init__(self):
        # 呼叫父類別初始化，設定 prefix 和 intents
        super().__init__(command_prefix='!', intents=intents)

    # 這就是你要的官方「初始化通道」
    async def setup_hook(self):
        self.db = await aiosqlite.connect('badminton.db')
        await self.create_tables()

        # 【關鍵】在這裡註冊你的 View，按鈕/選單才不會在重啟後失效
        self.add_view(await PaymentView.create(None))
        print("已註冊持久化視圖：PaymentView")

    async def create_tables(self):
        """建表邏輯，使用 self.db 操作"""
        await self.db.execute('''
                CREATE TABLE IF NOT EXISTS registration_log (
                    date TEXT,
                    name TEXT,
                    dc_id TEXT,
                    dc_name TEXT,
                    rank INTEGER,
                    pay INTEGER DEFAULT 0,
                    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, name, dc_id)
                )
            ''')
        
        await self.db.execute('''
                CREATE TABLE IF NOT EXISTS max_players (
                    date TEXT PRIMARY KEY,
                    max_count INTEGER
                )
            ''')
        await self.db.commit()
        print("📊 資料庫表格檢查完成")

    async def close(self):
        """當機器人關機時，確保資源被正確釋放"""
        if self.db:
            await self.db.close()
            print("🔒 資料庫連線已安全關閉")
        await super().close()


# 實例化你的機器人類別
bot = MyBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.event
async def on_member_join(member):
    await member.send(f'Welcome to the server, {member.name}!')

@bot.command()
@commands.has_role(ADMIN_ROLE_ID)
async def 開放報名(ctx, res_date: str, word: str, date_str: str, time_str: str = "23:59"):
    """
    用法範例：!設定截止 2026-02-22 22:00
    如果不輸入時間，預設為當天的 23:59
    """
    global deadline, reservation, reservation_date
    if word != "至":
        await ctx.send("❌ 格式錯誤！請使用 `!開放報名 YYYY-MM-DD 至 YYYY-MM-DD HH:MM` 格式。")
        return
    full_str = f"{date_str} {time_str}"
    
    try:
        # 資工核心：將字串轉換為 datetime 物件
        # %Y: 4位年, %m: 月, %d: 日, %H: 24小時制, %M: 分鐘
        deadline = datetime.strptime(full_str, "%Y-%m-%d %H:%M")
        reservation_date = res_date
        # 格式化輸出給使用者確認
        formatted_date = deadline.strftime("%Y年%m月%d日 %H:%M")
        reservation = True
        await ctx.send(f"✅ 報名截止時間已設定為：**{formatted_date}**")
        await bot.db.execute('''
            INSERT OR REPLACE INTO max_players (date, max_count) VALUES (?, ?)
        ''', (reservation_date, MAX_PLAYERS))
        await bot.db.commit()
    except ValueError:
        await ctx.send("❌ 格式錯誤！請使用 `!開放報名 YYYY-MM-DD 至 YYYY-MM-DD HH:MM` 格式。")
@開放報名.error
async def 開放報名_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("⚠️ 你沒有權限使用這個指令！")

@bot.command()
@commands.has_role(ADMIN_ROLE_ID)
async def 人數(ctx, count: int):
    global MAX_PLAYERS
    try:
        MAX_PLAYERS = count
        if reservation_date is None:
            await ctx.send("⚠️ 請先使用 `!開放報名` 指令設定報名日期，才能設定人數上限！")
            return
        await bot.db.execute('''
            INSERT OR REPLACE INTO max_players (date, max_count) VALUES (?, ?)
        ''', (reservation_date, count))
        await bot.db.commit()
        await ctx.send(f"已設定最大報名人數為 {MAX_PLAYERS} 人。")
    except ValueError:
        await ctx.send(f"❌ 請輸入有效的數字，例如：`!人數 5`")
@人數.error
async def 人數_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("⚠️ 你沒有權限使用這個指令！")

@bot.command()
@commands.has_role(ADMIN_ROLE_ID)
async def 結束報名(ctx):
    global deadline, reservation, reservation_date
    deadline = None
    reservation = False
    reservation_date = None
    await ctx.send("已結束報名。")
@結束報名.error
async def 結束報名_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("⚠️ 你沒有權限使用這個指令！")

# 繳費管理的 View
# 假設這是你的報名名單與繳費狀態（實務上建議存入資料庫）
# payments = {
#     "小明": False,
#     "小華": False,
#     "老張": False,
#     "小李": False,
#     "小王": False
# }

class PaymentView(View):
    def __init__(self, target_day):
        super().__init__(timeout=None)
        self.target_day = target_day
        
    @classmethod
    async def create(cls, target_day=None):
        self = cls(target_day)
        if target_day:
            await self.update_select_options()
        return self

    async def update_select_options(self):
        """根據名單狀態更新下拉選單的選項"""
        options = []
        cur = await bot.db.execute('''SELECT name, dc_id, dc_name, pay FROM registration_log WHERE date = ? ORDER BY inserted_at ASC''', (self.target_day,))
        payments_list = await cur.fetchall()
        cur_max = await bot.db.execute('''SELECT max_count FROM max_players WHERE date = ?''', (self.target_day,))
        max_players_row = await cur_max.fetchone()
        max_players = max_players_row[0] if max_players_row else MAX_PLAYERS  # 如果沒有設定人數上限，使用預設值
        payments_list = payments_list[:max_players]  # 只顯示前 MAX_PLAYERS 位
        if not payments_list:
            options.append(discord.SelectOption(
                label="目前沒有人報名！",
                description="當有成員報名後，才會在這裡顯示繳費狀態。",
                value="no_players",
                emoji="⚠️"
            ))
        for name, dc_id, dc_name, paid in payments_list:
            status = "已繳費" if paid == 1 else "未繳費"
            options.append(discord.SelectOption(
                label=f"{name} ({dc_name})", #實際看到
                description=f"目前狀態：{status}", 
                value=f"{name}|{dc_id}", #實際傳回用來查dictionary的key
                emoji="✅" if paid == 1 else "❌"
            ))
        
        # 移除舊選單並加入新選單
        self.clear_items()
        select = Select(custom_id="payment_select", placeholder="選擇成員來切換繳費狀態...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):

        user_role_ids = [role.id for role in interaction.user.roles]

        # 檢查使用者是否擁有 ADMIN_ROLE_ID
        if ADMIN_ROLE_ID not in user_role_ids:
            await interaction.response.send_message("⚠️ 你沒有權限修改繳費狀態！", ephemeral=True)
            return

        # 2. 【核心】如果 self.target_day 是 None，從 Embed 標題找回日期
        current_date = self.target_day
        if not current_date:
            try:
                # 假設標題是 "🏸 羽球團繳費清單 (2026-02-22)"
                title = interaction.message.embeds[0].title
                current_date = re.search(r"\d{4}-\d{2}-\d{2}", title).group()
                self.target_day = current_date # 找回記憶，存入 self
            except Exception:
                await interaction.response.send_message("❌ 無法辨識日期，請重新輸入 `!繳費` 產生新選單。", ephemeral=True)
                return
        # 取得被選擇的名字
        name = interaction.data['values'][0]
        select_name, select_dc_id = name.split("|")
        # 切換繳費狀態 (True -> False / False -> True)
        await bot.db.execute('''
            UPDATE registration_log 
            SET pay = 1 - pay 
            WHERE date = ? AND name = ? AND dc_id = ?
        ''', (current_date, select_name, select_dc_id))

        # 做完後手動存檔
        await bot.db.commit()
        
        # 更新選單內容與 Embed
        await self.update_select_options()
        new_embed = await self.create_embed()
        
        # 使用 edit_message 達成「原地更新」的效果，不會產生新訊息
        await interaction.response.edit_message(embed=new_embed, view=self)

    async def create_embed(self):
        """產生顯示繳費名單的 Embed"""
        embed = discord.Embed(title=f"🏸 羽球團繳費清單({self.target_day})", color=discord.Color.blue())
        content = ""
        cur = await bot.db.execute('''SELECT name, dc_name, pay FROM registration_log WHERE date = ? ORDER BY inserted_at ASC''', (self.target_day,))
        payments_list = await cur.fetchall()
        if not payments_list:
            content = "目前沒有人報名！"
        
        cur_max = await bot.db.execute('''SELECT max_count FROM max_players WHERE date = ?''', (self.target_day,))
        max_players_row = await cur_max.fetchone()
        max_players = max_players_row[0] if max_players_row else MAX_PLAYERS  # 如果沒有設定人數上限，使用預設值
        payments_list = payments_list[:max_players]  # 只顯示前 MAX_PLAYERS 位
        for name, dc_name, paid in payments_list:
            status = "✅ 已繳費" if paid else "❌ 未繳費"
            content += f"{name} ({dc_name})：{status}\n"
        embed.description = content
        return embed

@bot.command()
@commands.has_role(ADMIN_ROLE_ID)
async def 繳費(ctx , date: str = None):
    if date:
        pay_date = date
    else:
        if reservation_date is None:
            await ctx.send("請輸入要查的繳費名單日期，例如：!繳費 2025-04-05")
            return
        pay_date = reservation_date
    view = await PaymentView.create(pay_date)
    await ctx.send(embed=await view.create_embed(), view=view)
@繳費.error
async def 繳費_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("⚠️ 你沒有權限使用這個指令！")


def create_table_embed(data_dict, title="🏸 詳細報名表", players_num=None):
    embed = discord.Embed(title=title, color=discord.Color.green())
    
    # 分別建立「姓名」與「狀態」兩個直欄
    items = list(data_dict.items())
    players = items[:players_num] if players_num is not None else items[:MAX_PLAYERS]  # 只顯示前 MAX_PLAYERS 位
    waiting_list = items[players_num:] if players_num is not None else items[MAX_PLAYERS:]  # 超過 MAX_PLAYERS 的部分放到候補名單
    
    if players:
        players_str = ""
        for i, (name, dc_name) in enumerate(players, start=1):
            players_str += f"{i}. {name} ({dc_name})\n"
    else:
        players_str = "目前沒有人報名！"
    
    embed.add_field(name="報名名單", value=players_str, inline=False)
    
    if waiting_list:
        waiting_str = ""
        for i, (name, dc_name) in enumerate(waiting_list, start=1):
            waiting_str += f"{i}. {name} ({dc_name})\n"
        embed.add_field(name="候補名單", value=waiting_str, inline=False)

    return embed

@bot.event
async def on_message(message):
    # 1. 排除機器人自己的訊息，避免無窮迴圈
    if message.author == bot.user:
        return
    
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return
    
    if message.channel.id != RESERVATION_CHANNEL:
        await bot.process_commands(message)
        return

    # 2. 定義正規表示式 (Regex)
    # ^(.+)  -> 從開頭抓取任何字元（名字），直到遇到 +
    # \+     -> 匹配加號
    # (\d+)  -> 抓取後面的數字
    # $      -> 確保結尾沒有多餘字串
    match_add = re.search(r"^(.+)\s*\+\s*(\d+)\s*(?:\((\d+)\))?$", message.content)
    if match_add and reservation and (deadline is None or datetime.now() < deadline):
        # 用 .strip() 確保名字前後沒有殘留空白
        name = match_add.group(1).strip()
        count = int(match_add.group(2))
        rank = match_add.group(3)  # 可選的排名資訊，目前未使用

        await bot.db.execute('''
            INSERT OR REPLACE INTO registration_log (date, name, dc_id, dc_name,  rank)
            VALUES (?, ?, ?, ?, ?)
        ''', (reservation_date, name, str(message.author.id), str(message.author.display_name), rank))
    
        await bot.db.commit()
        # 3. 更新你的 payments 字典 (資料層)
        # 如果人名不在名單內，就新增進去，預設未繳費 (False)
        # if name not in payments:
        #     payments[name] = False
        #     action_text = "已加入名單並報名"
        # else:
        #     action_text = "更新報名人數為"

        await message.channel.send(f"✅ 收到！{name} 已報名。")
    
    match_remove = re.search(r"^(.+)\s*-\s*(\d+)$", message.content)
    if match_remove and reservation and (deadline is None or datetime.now() < deadline):
        name = match_remove.group(1).strip()
        count = int(match_remove.group(2))
        cur = await bot.db.execute(
            'SELECT dc_id FROM registration_log WHERE date = ? AND name = ?', 
            (reservation_date, name)
        )
        row = await cur.fetchone()


        if row:
            stored_dc_id = row[0]
            # 2. 檢查：發訊息者是「本人」 OR 擁有「管理員權限」
            is_admin = any(role.id == ADMIN_ROLE_ID for role in message.author.roles)
            
            if str(message.author.id) == stored_dc_id or is_admin:
                # 權限通過，執行刪除
                await bot.db.execute(
                    'DELETE FROM registration_log WHERE date = ? AND name = ?', 
                    (reservation_date, name)
                )
                await bot.db.commit()
                await message.channel.send(f"❌ 已取消 {name} 的報名。")
            else:
                # 權限不符
                await message.channel.send(f"⚠️ 你沒有權限取消 **{name}** 的報名！這筆資料是由其他成員登記的。")
        else:
            await message.channel.send(f"⚠️ 在名單中找不到 **{name}**。")
        # if name in payments:
        #     del payments[name]
        #     await message.channel.send(f"❌ 已從名單移除 {name}，共移除 {count} 位。")
        # else:
        #     await message.channel.send(f"⚠️ 名單中沒有找到 {name}，無法移除。")


    if match_add or match_remove:
        if reservation and (deadline is None or datetime.now() < deadline):
            cur = await bot.db.execute('''SELECT name, dc_name FROM registration_log WHERE date = ? ORDER BY inserted_at ASC''', (reservation_date,))
            payments_list = await cur.fetchall()
            payments_dict = {name: dc_name for name, dc_name in payments_list}
            new_embed = create_table_embed(payments_dict)
            await message.channel.send(embed=new_embed)

            # admin_channel = bot.get_channel(ADMIN_CHANNEL)
            # if admin_channel:
            #     view = PaymentView()
            #     await admin_channel.send(embed=view.create_embed(), view=view)
        else:
            await message.channel.send("⚠️ 目前不在報名期間，無法修改名單！")

    await bot.process_commands(message)

@bot.command()
async def 名單(ctx, date: str = None):
    if date is None:
        if reservation_date is None:
            await ctx.send("請輸入要查的名單日期，例如：!名單 2025-04-05")
            return
        date = reservation_date
    cur = await bot.db.execute('''SELECT name, dc_name FROM registration_log WHERE date = ? ORDER BY inserted_at ASC''', (date,))
    payments_list = await cur.fetchall()
    if not payments_list:
        await ctx.send(f"目前 {date} 沒有人報名！")
        return
    payments_dict = {name: dc_name for name, dc_name in payments_list}
    
    # 查詢該日期的最大人數限制
    cur_max = await bot.db.execute('''SELECT max_count FROM max_players WHERE date = ?''', (date,))
    max_players_row = await cur_max.fetchone()
    max_players = max_players_row[0] if max_players_row else MAX_PLAYERS  # 如果沒有設定人數上限，使用預設值

    embed = create_table_embed(payments_dict, players_num=max_players)
    await ctx.send(embed=embed)


bot.run(token, log_handler=handler, log_level=logging.DEBUG)