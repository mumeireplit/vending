from flask import Flask
import discord
from discord.ext import commands
from typing import Dict
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is running!'

# 商品データを保存する辞書
vending_items: Dict[str, Dict] = {
    "コーラ": {"price": 120, "stock": 5, "dm_messages": [], "used_messages": []},
    "お茶": {"price": 100, "stock": 5, "dm_messages": [], "used_messages": []},
    "水": {"price": 80, "stock": 5, "dm_messages": [], "used_messages": []}
}

# ユーザーのコインデータ
user_coins: Dict[int, int] = {}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class BuyButton(discord.ui.Button):
    def __init__(self, item_name: str, price: int):
        super().__init__(
            label=f"{item_name} ({price}コイン)",
            style=discord.ButtonStyle.primary
        )
        self.item_name = item_name
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in user_coins:
            user_coins[user_id] = 0
        
        if vending_items[self.item_name]["stock"] <= 0:
            await interaction.response.send_message("申し訳ありません。在庫切れです。", ephemeral=True)
            return
        
        if user_coins[user_id] < self.price:
            await interaction.response.send_message("コインが不足しています。", ephemeral=True)
            return
        
        user_coins[user_id] -= self.price
        vending_items[self.item_name]["stock"] -= 1
        await interaction.response.send_message(
            f"{self.item_name}を購入しました。\n所持コイン: {user_coins[user_id]}コイン\n残り在庫: {vending_items[self.item_name]['stock']}個\nDMをご確認ください。",
            ephemeral=True
        )
        
        import random
        available_messages = [msg for msg in vending_items[self.item_name]["dm_messages"] 
                            if msg not in vending_items[self.item_name]["used_messages"]]
        
        if available_messages:
            message = random.choice(available_messages)
            vending_items[self.item_name]["used_messages"].append(message)
            await interaction.user.send(message)
        else:
            await interaction.user.send("申し訳ありません。現在利用可能なシリアルコードがありません。")

class VendingView(discord.ui.View):
    def __init__(self):
        super().__init__()
        for item_name, details in vending_items.items():
            self.add_item(BuyButton(item_name, details["price"]))

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました')

@bot.command(name="vending")
async def help_command(ctx, arg="help"):
    if arg == "help":
        embed = discord.Embed(title="自動販売機ボットの使い方", color=0x00ff00)
        
        # 一般ユーザー向けコマンド
        embed.add_field(
            name="一般コマンド",
            value="""
            `!show` - 商品一覧と購入ボタンを表示
            `!coincheck` - 所持コインを確認
            """,
            inline=False
        )
        
        # 管理者向けコマンド
        embed.add_field(
            name="管理者コマンド（8j1uとmume_dayoのみ使用可能）",
            value="""
            `!addcoins @メンバー 数値` - メンバーにコインを追加
            `!newitem 商品名 価格 在庫数` - 新しい商品を追加（在庫数はオプション、デフォルト5）
            `!add 商品名 1:メッセージ1 2:メッセージ2` - 商品にDMメッセージを追加
            `!del 商品名` - 商品を削除
            """,
            inline=False
        )
        
        await ctx.send(embed=embed)

@bot.command(name="show")
async def list_items(ctx):
    embed = discord.Embed(title="自動販売機の商品一覧", color=0x00ff00)
    for item, details in vending_items.items():
        embed.add_field(
            name=item,
            value=f"価格: {details['price']}コイン\n在庫: {details['stock']}個",
            inline=False
        )
    view = VendingView()
    await ctx.send(embed=embed, view=view)

def is_authorized():
    async def predicate(ctx):
        allowed_users = ["8j1u", "mume_dayo"]
        return ctx.author.name in allowed_users
    return commands.check(predicate)

@bot.command(name="addcoins")
@is_authorized()
async def add_coins(ctx, member: discord.Member, amount: int):
    user_id = member.id
    if user_id not in user_coins:
        user_coins[user_id] = 0
    user_coins[user_id] += amount
    await ctx.send(f"{member.mention}に{amount}コインを追加しました。\n現在の所持コイン: {user_coins[user_id]}コイン")

@bot.command(name="coincheck")
async def check_coins(ctx):
    user_id = ctx.author.id
    coins = user_coins.get(user_id, 0)
    await ctx.send(f"現在の所持コイン: {coins}コイン")

@bot.command(name="newitem")
@is_authorized()
async def add_new_item(ctx, item_name: str, price: int, stock: int = 5):
    if item_name in vending_items:
        await ctx.send("その商品は既に存在します。")
        return
    
    vending_items[item_name] = {
        "price": price,
        "stock": stock,
        "dm_messages": [],
        "used_messages": []
    }
    await ctx.send(f"新商品「{item_name}」を追加しました。\n価格: {price}コイン\n在庫: {stock}個")

@bot.command(name="del")
@is_authorized()
async def delete_item(ctx, item_name: str):
    if item_name not in vending_items:
        await ctx.send("その商品は存在しません。")
        return
    
    del vending_items[item_name]
    await ctx.send(f"{item_name}を削除しました。")

@bot.command(name="add")
@is_authorized()
async def add_item_messages(ctx, item_name: str, *messages):
    if item_name not in vending_items:
        await ctx.send("その商品は存在しません。")
        return
    
    if "dm_messages" not in vending_items[item_name]:
        vending_items[item_name]["dm_messages"] = []
    
    added_messages = []
    for msg in messages:
        if ':' in msg:
            try:
                num, content = msg.split(':', 1)
                if content:  # 内容が空でない場合のみ追加
                    added_messages.append(content)
            except ValueError:
                continue
    
    if added_messages:
        vending_items[item_name]["dm_messages"].extend(added_messages)
        await ctx.send(f"{item_name}に{len(added_messages)}個のメッセージを追加しました。\n現在のメッセージ数: {len(vending_items[item_name]['dm_messages'])}個")
    else:
        await ctx.send("追加するメッセージがありませんでした。")

def run_discord_bot():
    bot.run(os.getenv('DISCORD_TOKEN'))

if __name__ == "__main__":
    # Discordボットを別スレッドで実行
    bot_thread = threading.Thread(target=run_discord_bot)
    bot_thread.start()
    
    # FlaskサーバーをPort 8080で実行
    app.run(host='0.0.0.0', port=8080)
