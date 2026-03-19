import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
from datetime import datetime
import uuid
import asyncio

# 1. BOT TOKEN - @BotFather dan olgan tokeningizni qo'ying
TOKEN = "8295217817:AAG1tB9Izs-8RIuL-4_m7OVeDqNLZDdONqI"  # O'Z TOKENINGIZNI YOZING

# 2. ADMIN ID - @userinfobot dan olgan ID ingizni qo'ying
ADMIN_ID = 6713905538  # O'Z ID INGIZNI YOZING

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
def init_db():
    conn = sqlite3.connect('pubg_uc_bot.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                  registered_date TEXT, total_spent REAL DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, uc_amount INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (order_id TEXT PRIMARY KEY, user_id INTEGER, product_id INTEGER, 
                  amount REAL, uc_amount INTEGER, status TEXT, date TEXT, payment_method TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        default_products = [
            ("60 UC", 6000, 60),
            ("300 UC + 25 Bonus", 29000, 325),
            ("600 UC + 60 Bonus", 57000, 660),
            ("1500 UC + 200 Bonus", 140000, 1700),
            ("3000 UC + 500 Bonus", 275000, 3500)
        ]
        c.executemany("INSERT INTO products (name, price, uc_amount) VALUES (?, ?, ?)", default_products)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, registered_date) VALUES (?, ?, ?, ?)",
                  (user.id, user.username, user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")
    
    keyboard = [
        [InlineKeyboardButton("🛒 UC Sotib olish", callback_data="buy_uc")],
        [InlineKeyboardButton("📜 Mening buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="contact_admin")]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Assalomu alaykum {user.first_name}!\n\n"
        f"PUBG UC do'koniga xush kelibsiz!\n"
        f"Quyidagi tugmalardan birini tanlang:",
        reply_markup=reply_markup
    )

# Buy UC
async def buy_uc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("SELECT id, name, price, uc_amount FROM products")
        products = c.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")
        await query.edit_message_text("Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")
        return
    
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            f"{product[1]} - {product[2]} so'm ({product[3]} UC)", 
            callback_data=f"select_product_{product[0]}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Quyidagi UC paketlaridan birini tanlang:",
        reply_markup=reply_markup
    )

# Select product
async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        product_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("SELECT name, price, uc_amount FROM products WHERE id=?", (product_id,))
        product = c.fetchone()
        conn.close()
        
        if not product:
            await query.edit_message_text("Mahsulot topilmadi.")
            return
        
        context.user_data['selected_product'] = {
            'id': product_id,
            'name': product[0],
            'price': product[1],
            'uc_amount': product[2]
        }
        
        keyboard = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_order")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="buy_uc")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Tanlangan paket: {product[0]}\n"
            f"Narxi: {product[1]} so'm\n"
            f"UC miqdori: {product[2]} UC\n\n"
            f"Buyurtmani tasdiqlaysizmi?",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in select_product: {e}")
        await query.edit_message_text("Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

# Confirm order
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product = context.user_data.get('selected_product')
    if not product:
        await query.edit_message_text("Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")
        return
    
    order_id = str(uuid.uuid4())[:8].upper()
    
    keyboard = [
        [InlineKeyboardButton("💳 Click", callback_data=f"pay_click_{order_id}")],
        [InlineKeyboardButton("💳 Payme", callback_data=f"pay_payme_{order_id}")],
        [InlineKeyboardButton("💳 Uzum Bank", callback_data=f"pay_uzum_{order_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🆕 Buyurtma ID: {order_id}\n"
        f"Paket: {product['name']}\n"
        f"To'lov summasi: {product['price']:,} so'm\n\n"
        f"To'lov usulini tanlang:",
        reply_markup=reply_markup
    )

# Payment
async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    method = data[1]
    order_id = data[2]
    
    product = context.user_data.get('selected_product')
    user = update.effective_user
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("""INSERT INTO orders 
                    (order_id, user_id, product_id, amount, uc_amount, status, date, payment_method) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (order_id, user.id, product['id'], product['price'], product['uc_amount'], 
                   'waiting_payment', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), method))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error in payment: {e}")
        await query.edit_message_text("Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")
        return
    
    payment_details = {
        'click': "💳 Click to'lov\n\nKarta: 8600 1234 5678 9012\nTo'lov summasi: {} so'm\n\nTo'lovni amalga oshirgach, chekni yuboring.",
        'payme': "💳 Payme to'lov\n\nKarta: 8600 1234 5678 9012\nTo'lov summasi: {} so'm\n\nTo'lovni amalga oshirgach, chekni yuboring.",
        'uzum': "💳 Uzum Bank to'lov\n\nKarta: 8600 1234 5678 9012\nTo'lov summasi: {} so'm\n\nTo'lovni amalga oshirgach, chekni yuboring."
    }
    
    await query.edit_message_text(
        f"🆔 Buyurtma ID: {order_id}\n\n"
        f"{payment_details[method].format(product['price'])}"
    )
    
    context.user_data['waiting_payment'] = order_id

# Handle payment proof
async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    order_id = context.user_data.get('waiting_payment')
    
    if not order_id:
        await update.message.reply_text("Sizda faol buyurtma mavjud emas.")
        return
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE order_id=?", (order_id,))
        order = c.fetchone()
        
        if not order:
            conn.close()
            await update.message.reply_text("Buyurtma topilmadi.")
            return
        
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=update.message.photo[-1].file_id,
                caption=f"🆕 Yangi to'lov cheki!\n"
                        f"Buyurtma ID: {order_id}\n"
                        f"Foydalanuvchi: {user.full_name} (@{user.username})\n"
                        f"User ID: {user.id}\n"
                        f"Summa: {order[4]} so'm\n"
                        f"To'lov usuli: {order[7]}"
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🆕 Yangi to'lov cheki!\n"
                     f"Buyurtma ID: {order_id}\n"
                     f"Foydalanuvchi: {user.full_name} (@{user.username})\n"
                     f"User ID: {user.id}\n"
                     f"Summa: {order[4]} so'm\n"
                     f"To'lov usuli: {order[7]}\n\n"
                     f"Chek: {update.message.text}"
            )
        
        c.execute("UPDATE orders SET status='pending_approval' WHERE order_id=?", (order_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ To'lov chekingiz adminga yuborildi!\n"
            "Admin tomonidan tekshirilgach, UC hisobingizga tushiriladi."
        )
        
        context.user_data.pop('waiting_payment')
        
    except Exception as e:
        logger.error(f"Error in payment proof: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Iltimos admin bilan bog'laning.")

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("Siz admin emassiz!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton("➕ Mahsulot qo'shish", callback_data="admin_add_product")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👨‍💼 Admin panelga xush kelibsiz!\nKerakli bo'limni tanlang:",
        reply_markup=reply_markup
    )

# Admin statistics
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM orders")
        total_orders = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")
        completed_orders = c.fetchone()[0]
        
        c.execute("SELECT SUM(amount) FROM orders WHERE status='completed'")
        total_revenue = c.fetchone()[0] or 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*), SUM(amount) FROM orders WHERE date LIKE ? AND status='completed'", (f"{today}%",))
        today_data = c.fetchone()
        
        conn.close()
        
        stats_text = (
            f"📊 BOT STATISTIKASI\n\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"📦 Jami buyurtmalar: {total_orders}\n"
            f"✅ Tasdiqlangan: {completed_orders}\n"
            f"💰 Jami daromad: {total_revenue:,.0f} so'm\n\n"
            f"📅 Bugungi buyurtmalar:\n"
            f"  - Soni: {today_data[0] or 0}\n"
            f"  - Summa: {today_data[1] or 0:,.0f} so'm"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}")
        await query.edit_message_text("Xatolik yuz berdi.")

# Admin orders
async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE status='pending_approval' ORDER BY date DESC LIMIT 5")
        orders = c.fetchall()
        conn.close()
        
        if not orders:
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Hozircha kutilayotgan buyurtmalar yo'q.", reply_markup=reply_markup)
            return
        
        order = orders[0]
        order_text = (
            f"🆔 Buyurtma ID: {order[0]}\n"
            f"👤 User ID: {order[1]}\n"
            f"💰 Summa: {order[4]:,.0f} so'm\n"
            f"🎮 UC: {order[5]}\n"
            f"📅 Sana: {order[6]}\n"
            f"💳 To'lov: {order[7]}\n"
            f"📊 Status: {order[3]}\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_order_{order[0]}"),
             InlineKeyboardButton("❌ Bekor qilish", callback_data=f"reject_order_{order[0]}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(order_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_orders: {e}")
        await query.edit_message_text("Xatolik yuz berdi.")

# Approve order
async def approve_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        order_id = query.data.split('_')[2]
        
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("UPDATE orders SET status='completed' WHERE order_id=?", (order_id,))
        c.execute("SELECT user_id, amount, uc_amount FROM orders WHERE order_id=?", (order_id,))
        order = c.fetchone()
        
        if order:
            c.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id=?", (order[1], order[0]))
        
        conn.commit()
        conn.close()
        
        if order:
            await context.bot.send_message(
                chat_id=order[0],
                text=f"✅ Hurmatli foydalanuvchi!\n"
                     f"Sizning {order[2]} UC uchun buyurtmangiz tasdiqlandi!\n"
                     f"UC lar hisobingizga tushirildi. O'yindan rohatlaning!"
            )
        
        await query.edit_message_text(f"✅ Buyurtma {order_id} tasdiqlandi!")
        
        await asyncio.sleep(1)
        await admin_panel(update, context)
        
    except Exception as e:
        logger.error(f"Error in approve_order: {e}")
        await query.edit_message_text("Xatolik yuz berdi.")

# Reject order
async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        order_id = query.data.split('_')[2]
        
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("UPDATE orders SET status='rejected' WHERE order_id=?", (order_id,))
        c.execute("SELECT user_id FROM orders WHERE order_id=?", (order_id,))
        user_id = c.fetchone()[0]
        conn.commit()
        conn.close()
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Kechirasiz, sizning {order_id} - buyurtmangiz bekor qilindi.\n"
                 f"Iltimos admin bilan bog'lanib, qayta urinib ko'ring."
        )
        
        await query.edit_message_text(f"❌ Buyurtma {order_id} bekor qilindi!")
        
        await asyncio.sleep(1)
        await admin_panel(update, context)
        
    except Exception as e:
        logger.error(f"Error in reject_order: {e}")
        await query.edit_message_text("Xatolik yuz berdi.")

# Main menu
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🛒 UC Sotib olish", callback_data="buy_uc")],
        [InlineKeyboardButton("📜 Mening buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("📞 Admin bilan bog'lanish", callback_data="contact_admin")]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Assalomu alaykum {user.first_name}!\n\n"
        f"PUBG UC do'koniga xush kelibsiz!\n"
        f"Quyidagi tugmalardan birini tanlang:",
        reply_markup=reply_markup
    )

# My orders
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("SELECT order_id, amount, uc_amount, status, date FROM orders WHERE user_id=? ORDER BY date DESC LIMIT 10", (user_id,))
        orders = c.fetchall()
        conn.close()
        
        if not orders:
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Siz hali hech qanday buyurtma bermagansiz.", reply_markup=reply_markup)
            return
        
        orders_text = "📜 SIZNING BUYURTMALARINGIZ:\n\n"
        for order in orders:
            status_emoji = {
                'waiting_payment': '⏳',
                'pending_approval': '🔄',
                'completed': '✅',
                'rejected': '❌'
            }.get(order[3], '❓')
            
            orders_text += f"{status_emoji} ID: {order[0]}\n"
            orders_text += f"   UC: {order[2]}, Narx: {order[1]:,.0f} so'm\n"
            orders_text += f"   Sana: {order[4]}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(orders_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in my_orders: {e}")
        await query.edit_message_text("Xatolik yuz berdi.")

# Contact admin
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📞 Admin bilan bog'lanish\n\n"
        f"Admin bilan bog'lanish uchun ushbu kontakt orqali murojaat qiling:\n"
        f"👤 Admin: @admin_username\n"
        f"🆔 Admin ID: {ADMIN_ID}\n\n"
        f"Savol yoki muammo bo'lsa, bemalol yozing!",
        reply_markup=reply_markup
    )

# Admin add product
async def admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    await query.edit_message_text(
        "➕ Yangi mahsulot qo'shish\n\n"
        "Quyidagi formatda yuboring:\n"
        "Mahsulot nomi, Narxi, UC miqdori\n\n"
        "Misol: 60 UC, 6000, 60\n"
        "Misol: 300 UC + Bonus, 29000, 325"
    )
    context.user_data['adding_product'] = True

# Admin users
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        conn = sqlite3.connect('pubg_uc_bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name, registered_date, total_spent FROM users ORDER BY registered_date DESC LIMIT 10")
        users = c.fetchall()
        conn.close()
        
        users_text = "👥 OXIRGI 10 FOYDALANUVCHI:\n\n"
        for user in users:
            users_text += f"🆔 ID: {user[0]}\n"
            users_text += f"👤 Ism: {user[2]}\n"
            users_text += f"📧 Username: @{user[1] if user[1] else 'No username'}\n"
            users_text += f"📅 Ro'yxatdan o'tgan: {user[3]}\n"
            users_text += f"💰 Jami xarajat: {user[4]:,.0f} so'm\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(users_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_users: {e}")
        await query.edit_message_text("Xatolik yuz berdi.")

# Handle product addition
async def handle_product_addition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('adding_product') and update.effective_user.id == ADMIN_ID:
        try:
            text = update.message.text
            parts = text.split(',')
            if len(parts) == 3:
                name = parts[0].strip()
                price = float(parts[1].strip())
                uc = int(parts[2].strip())
                
                conn = sqlite3.connect('pubg_uc_bot.db')
                c = conn.cursor()
                c.execute("INSERT INTO products (name, price, uc_amount) VALUES (?, ?, ?)",
                          (name, price, uc))
                conn.commit()
                conn.close()
                
                await update.message.reply_text(f"✅ Mahsulot qo'shildi:\n{name}\nNarxi: {price:,.0f} so'm\nUC: {uc}")
                context.user_data.pop('adding_product')
            else:
                await update.message.reply_text(
                    "❌ Noto'g'ri format.\n\n"
                    "To'g'ri format: Mahsulot nomi, Narxi, UC miqdori\n"
                    "Misol: 60 UC, 6000, 60"
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {str(e)}")

# Handle unknown messages
async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Iltimos, tugmalardan foydalaning yoki /start ni bosing."
    )

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main function - PYTHON 3.14 UCHUN TO'G'RILANGAN
async def main():
    init_db()
    
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(buy_uc, pattern="^buy_uc$"))
    application.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    application.add_handler(CallbackQueryHandler(contact_admin, pattern="^contact_admin$"))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_orders, pattern="^admin_orders$"))
    application.add_handler(CallbackQueryHandler(admin_add_product, pattern="^admin_add_product$"))
    application.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    application.add_handler(CallbackQueryHandler(select_product, pattern="^select_product_"))
    application.add_handler(CallbackQueryHandler(confirm_order, pattern="^confirm_order$"))
    application.add_handler(CallbackQueryHandler(payment, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(approve_order, pattern="^approve_order_"))
    application.add_handler(CallbackQueryHandler(reject_order, pattern="^reject_order_"))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_addition))
    application.add_handler(MessageHandler(filters.PHOTO, handle_payment_proof))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_proof))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))
    
    application.add_error_handler(error_handler)
    
    print("🤖 Bot ishga tushdi...")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print(f"🔑 Token: {TOKEN[:10]}...")
    print("📊 Bot ishlamoqda...")
    
    # Python 3.14 uchun to'g'ri ishga tushirish
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Botni to'xtatishgacha ishlatish
    try:
        # Infinite loop
        while True:
            await asyncio.sleep(1)  # 1 soat uxlab, qayta tekshirish
    except KeyboardInterrupt:
        # Ctrl+C bosilganda
        print("\n🛑 Bot to'xtatilmoqda...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    # Python 3.14 uchun event loop yaratish
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n👋 Bot to'xtatildi")
    finally:
        loop.close()
