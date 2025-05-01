import logging
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TOKEN = '8051065968:AAHNC7qlJoMnxu5MP10O-xeQ8HZGHNV-LaU'  # Replace with your actual bot token
DB = 'db.sqlite'
QR_IMAGE = 'https://t.me/plinkkkkkkkkk/2'  # Replace with actual QR image

# States
ASK_NAME, ASK_LINK, SELECT_OFFER_STATE, ASK_USERNAME, ASK_PHONE, ASK_TXID, DELETE_OFFER_STATE = range(7)

# DB Setup
def init_db():
    with sqlite3.connect(DB) as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY,
                name TEXT,
                img TEXT
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                user_id INT,
                username TEXT,
                phone TEXT,
                offer TEXT,
                txid TEXT,
                status TEXT DEFAULT "pending"
            )
        ''')
        db.commit()

# Admin: Add new offer
async def addimg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Send Offer Name:')
    return ASK_NAME

async def ask_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text('Send Image URL:')
    return ASK_LINK

async def save_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name, img = context.user_data['name'], update.message.text
    with sqlite3.connect(DB) as db:
        db.execute('INSERT INTO offers (name, img) VALUES (?, ?)', (name, img))
        db.commit()
    await update.message.reply_text(f"✅ Offer '{name}' added!")
    return ConversationHandler.END

# Admin: Delete offer
async def delete_offer_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with sqlite3.connect(DB) as db:
        offers = db.execute('SELECT id, name FROM offers').fetchall()
    if not offers:
        await update.message.reply_text('No offers available to delete.')
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(name, callback_data=f'delete:{id}')] for id, name in offers]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Which offer do you want to delete?', reply_markup=reply_markup)
    return DELETE_OFFER_STATE

async def delete_offer_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    offer_id = query.data.split(':')[1]
    context.user_data['delete_offer_id'] = offer_id
    keyboard = [[InlineKeyboardButton('Yes, Delete!', callback_data='confirm_delete'),
                 InlineKeyboardButton('No, Cancel', callback_data='cancel_delete')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(f'Are you sure you want to delete offer ID {offer_id}?', reply_markup=reply_markup)
    return DELETE_OFFER_STATE

async def delete_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'confirm_delete':
        offer_id = context.user_data.get('delete_offer_id')
        if offer_id:
            with sqlite3.connect(DB) as db:
                db.execute('DELETE FROM offers WHERE id=?', (offer_id,))
                db.commit()
            await query.message.edit_text(f'✅ Offer ID {offer_id} deleted!')
        else:
            await query.message.edit_text('⚠️ Error: Offer ID not found.')
    else:
        await query.message.edit_text('❌ Deletion canceled.')
    return ConversationHandler.END

async def cancel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.edit_text('❌ Deletion canceled.')
    return ConversationHandler.END

# User Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with sqlite3.connect(DB) as db:
        offers = db.execute('SELECT name, img FROM offers').fetchall()
    if not offers:
        await update.message.reply_text('No offers available.')
        return ConversationHandler.END
    for name, img in offers:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Select Offer", callback_data=f'select:{name}')]])
        await update.message.reply_photo(photo=img, caption=name, reply_markup=btn)
    return SELECT_OFFER_STATE

async def select_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['offer'] = query.data.split(':')[1]
    await query.message.reply_text('Send your Instagram username (without @):')
    return ASK_USERNAME

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['username'] = update.message.text
    await update.message.reply_text('📞 Please enter your phone number:')
    return ASK_PHONE

async def ask_txid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['phone'] = update.message.text
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton('✅ Paid', callback_data='paid')],
        [InlineKeyboardButton('❌ Cancel', callback_data='cancel')]
    ])
    await update.message.reply_photo(
        photo=QR_IMAGE,
        caption="Scan QR and pay via PhonePe or GooglePay.\nClick ✅ when done.",
        reply_markup=btn
    )
    return SELECT_OFFER_STATE

async def paid_or_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'cancel':
        await query.message.reply_text('Order canceled.')
        return ConversationHandler.END
    elif query.data == 'paid':
        await query.message.reply_text('Send Transaction ID:')
        return ASK_TXID
    return SELECT_OFFER_STATE

async def save_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    username = context.user_data['username']
    phone = context.user_data['phone']
    offer = context.user_data['offer']
    txid = update.message.text

    with sqlite3.connect(DB) as db:
        db.execute(
            'INSERT INTO orders (user_id, username, phone, offer, txid) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, phone, offer, txid)
        )
        db.commit()

    await update.message.reply_text('✅ Payment Confirmed! Your order is processing.')
    return ConversationHandler.END

# Admin: View orders
async def vieworders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with sqlite3.connect(DB) as db:
        orders = db.execute('SELECT id, username, phone, offer FROM orders WHERE status="pending"').fetchall()
    if not orders:
        await update.message.reply_text('No pending orders.')
        return
    for oid, user, phone, offer in orders:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton('✅ Finish', callback_data=f'finish:{oid}')]])
        await update.message.reply_text(
            f"📦 Order #{oid}\n👤 Username: @{user}\n📞 Phone: {phone}\n🎁 Offer: {offer}",
            reply_markup=btn
        )

async def finish_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    oid = query.data.split(':')[1]
    with sqlite3.connect(DB) as db:
        user_id = db.execute('SELECT user_id FROM orders WHERE id=?', (oid,)).fetchone()
        if user_id:
            try:
                await context.bot.send_message(chat_id=user_id[0], text='🎉 Your order is completed!')
                db.execute('UPDATE orders SET status="done" WHERE id=?', (oid,))
                db.commit()
                await query.message.edit_text('✅ Order marked as finished.')
            except Exception as e:
                logger.error(f"Error: {e}")
                await query.message.edit_text('⚠️ Error processing order.')
        else:
            await query.message.edit_text('❌ Order not found.')

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Canceled.')
    return ConversationHandler.END

def main() -> None:
    init_db()
    app = Application.builder().token(TOKEN).build()

    # Add image (admin)
    add_offer_handler = ConversationHandler(
        entry_points=[CommandHandler('addimg', addimg)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_link)],
            ASK_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_offer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Delete image (admin)
    delete_offer_handler = ConversationHandler(
        entry_points=[CommandHandler('dlt', delete_offer_start)],
        states={
            DELETE_OFFER_STATE: [
                CallbackQueryHandler(delete_offer_confirm, pattern='^delete:'),
                CallbackQueryHandler(delete_offer, pattern='^confirm_delete$'),
                CallbackQueryHandler(cancel_delete, pattern='^cancel_delete$'),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Place order (user)
    order_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_OFFER_STATE: [
                CallbackQueryHandler(select_offer, pattern='^select:'),
                CallbackQueryHandler(paid_or_cancel, pattern='^(paid|cancel)$')
            ],
            ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_txid)],
            ASK_TXID: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_order)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Add handlers
    app.add_handler(add_offer_handler)
    app.add_handler(delete_offer_handler)
    app.add_handler(order_handler)
    app.add_handler(CommandHandler('vieworders', vieworders))
    app.add_handler(CallbackQueryHandler(finish_order, pattern='^finish:'))

    print('Bot running...')
    app.run_polling()

if __name__ == '__main__':
    main()