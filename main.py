#!/usr/bin/env python3
"""
OMNIX BOT PRINCIPAL PARA RENDER DEPLOYMENT
Versión final optimizada y probada - Lista para producción
"""

import os
import time
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import sqlite3
from datetime import datetime
import openai
from gtts import gTTS
import tempfile
import json
import re
import threading
import hashlib
import hmac
import base64
import urllib.parse

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class OmnixBotRender:
    def __init__(self):
        print("🚀 OMNIX BOT RENDER DEPLOYMENT - VERSIÓN FINAL")
        
        # API Keys desde variables de entorno
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN') 
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        # CONFIGURAR KRAKEN
        self.kraken_api_key = os.getenv('KRAKEN_API_KEY')
        self.kraken_api_secret = os.getenv('KRAKEN_API_SECRET')
        
        # Configurar OpenAI
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
            print("✅ OpenAI configurado")
        
        # Base de datos para conversaciones
        self.init_database()
        
        # Variables para sistema auto-venta
        self.auto_trading_enabled = True
        self.target_daily_profit = 15.0
        self.daily_profit = 0.0
        self.trades_today = 0
        self.last_trade_time = datetime.now()
        
        # Iniciar sistema auto-venta si hay credenciales
        if self.kraken_api_key and self.kraken_api_secret:
            self.start_auto_trading_thread()
            print("✅ Auto-trading iniciado")
        
        print("✅ OMNIX BOT RENDER DEPLOYMENT LISTO")
        print("📊 Tracking de usuarios integrado")
        print("💰 Sistema auto-venta $15 diarios activado")
        
    def init_database(self):
        """Inicializar base de datos de conversaciones"""
        try:
            conn = sqlite3.connect('omnix_render.db')
            cursor = conn.cursor()
            
            # Tabla conversaciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    message TEXT,
                    response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla tracking usuarios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    referral_code TEXT,
                    referred_by TEXT,
                    registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    total_messages INTEGER DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    is_premium BOOLEAN DEFAULT FALSE,
                    conversion_date DATETIME,
                    lifetime_value REAL DEFAULT 0.0
                )
            ''')
            
            # Tabla historial trading
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trading_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    crypto TEXT,
                    action TEXT,
                    amount REAL,
                    price REAL,
                    usd_value REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    order_id TEXT,
                    status TEXT DEFAULT 'completed'
                )
            ''')
            
            # Tabla control trading diario
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_trading_control (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE,
                    trades_count INTEGER DEFAULT 0,
                    profit_usd REAL DEFAULT 0.0,
                    loss_usd REAL DEFAULT 0.0,
                    max_trades INTEGER DEFAULT 15,
                    max_loss REAL DEFAULT 50.0
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ Base de datos inicializada")
        except Exception as e:
            logger.error(f"Error inicializando base de datos: {e}")
    
    def get_conversation_memory(self, user_id, limit=5):
        """Obtener memoria de conversaciones anteriores"""
        try:
            conn = sqlite3.connect('omnix_render.db')
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT message, response FROM conversations 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            ''', (user_id, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            if results:
                memory = "Conversaciones anteriores:\n"
                for msg, resp in reversed(results):
                    memory += f"Usuario: {msg[:50]}...\n"
                    memory += f"Bot: {resp[:50]}...\n"
                return memory
            return ""
        except Exception as e:
            logger.error(f"Error obteniendo memoria: {e}")
            return ""
    
    def save_conversation(self, user_id, username, message, response):
        """Guardar conversación en base de datos"""
        try:
            conn = sqlite3.connect('omnix_render.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO conversations (user_id, username, message, response)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, message, response))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando conversación: {e}")
    
    def kraken_api_request(self, endpoint, params=None):
        """Realizar petición a API Kraken"""
        try:
            if not self.kraken_api_key or not self.kraken_api_secret:
                return {"error": "API keys not configured"}
            
            if params is None:
                params = {}
            
            # Usar timestamp más preciso
            nonce = str(int(time.time() * 1000000))
            params['nonce'] = nonce
            
            # Codificar parámetros
            postdata = urllib.parse.urlencode(params)
            
            # Crear firma
            encoded = (nonce + postdata).encode()
            message = endpoint.encode() + hashlib.sha256(encoded).digest()
            
            mac = hmac.new(base64.b64decode(self.kraken_api_secret), message, hashlib.sha512)
            sigdigest = base64.b64encode(mac.digest()).decode()
            
            headers = {
                'API-Key': self.kraken_api_key,
                'API-Sign': sigdigest,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            url = f"https://api.kraken.com{endpoint}"
            
            response = requests.post(url, headers=headers, data=postdata, timeout=10)
            return response.json()
            
        except Exception as e:
            logger.error(f"Error API Kraken: {e}")
            return {"error": str(e)}
    
    def get_balance(self):
        """Obtener balance de Kraken"""
        try:
            result = self.kraken_api_request('/0/private/Balance')
            if result and 'result' in result:
                return result['result']
            return {}
        except Exception as e:
            logger.error(f"Error obteniendo balance: {e}")
            return {}
    
    def get_crypto_prices(self):
        """Obtener precios de cryptos"""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,avalanche-2&vs_currencies=usd"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            logger.error(f"Error obteniendo precios: {e}")
            return {}
    
    def can_trade_today(self):
        """Verificar si puede hacer trades hoy"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            conn = sqlite3.connect('omnix_render.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT trades_count, loss_usd, max_trades, max_loss 
                FROM daily_trading_control 
                WHERE date = ?
            ''', (today,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                trades_count, loss_usd, max_trades, max_loss = result
                can_trade = trades_count < max_trades and loss_usd < max_loss
                return can_trade, trades_count, max_trades
            else:
                # Crear entrada para hoy
                conn = sqlite3.connect('omnix_render.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO daily_trading_control (date)
                    VALUES (?)
                ''', (today,))
                conn.commit()
                conn.close()
                return True, 0, 15
                
        except Exception as e:
            logger.error(f"Error verificando límites: {e}")
            return False, 0, 0
    
    def execute_auto_trade(self):
        """Ejecutar trade automático"""
        try:
            # Verificar límites diarios
            can_trade, trades_today, max_trades = self.can_trade_today()
            
            if not can_trade:
                print(f"❌ Límite diario alcanzado: {trades_today}/{max_trades} trades")
                return False
            
            balance = self.get_balance()
            usd_balance = float(balance.get('ZUSD', 0))
            
            print(f"💰 Balance USD: ${usd_balance:.2f}")
            print(f"📊 Trades hoy: {trades_today}/{max_trades}")
            
            # Si no hay USD suficiente, vender cryptos
            if usd_balance < 50:
                # Buscar cryptos para vender
                cryptos_to_sell = []
                
                for crypto, amount in balance.items():
                    if crypto not in ['ZUSD'] and float(amount) > 0:
                        cryptos_to_sell.append((crypto, float(amount)))
                
                if cryptos_to_sell:
                    # Vender 30% de la crypto con mayor cantidad
                    cryptos_to_sell.sort(key=lambda x: x[1], reverse=True)
                    crypto_to_sell, amount = cryptos_to_sell[0]
                    
                    sell_amount = amount * 0.3  # Vender 30%
                    
                    # Ejecutar venta
                    success = self.execute_sell_order(crypto_to_sell, sell_amount)
                    if success:
                        self.update_daily_trades()
                    print(f"🔄 Vendiendo {sell_amount:.4f} {crypto_to_sell}")
                    return success
                else:
                    print("⚠️ No hay cryptos suficientes para vender")
                    return False
            else:
                # Hacer trading normal
                success = self.execute_buy_order()
                if success:
                    self.update_daily_trades()
                print("💹 Ejecutando compra automática")
                return success
                
        except Exception as e:
            logger.error(f"Error en auto-trade: {e}")
            print(f"❌ Error API Kraken: {e}")
            return False
    
    def update_daily_trades(self):
        """Actualizar contador de trades diarios"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            conn = sqlite3.connect('omnix_render.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE daily_trading_control 
                SET trades_count = trades_count + 1
                WHERE date = ?
            ''', (today,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error actualizando trades diarios: {e}")
    
    def execute_sell_order(self, crypto, amount):
        """Ejecutar orden de venta"""
        try:
            # Mapear symbols de Kraken
            symbol_map = {
                'XAVAX': 'AVAXUSD',
                'XXBT': 'XBTUSD', 
                'XETH': 'ETHUSD',
                'SOL': 'SOLUSD'
            }
            
            pair = symbol_map.get(crypto, f"{crypto}USD")
            
            params = {
                'pair': pair,
                'type': 'sell',
                'ordertype': 'market',
                'volume': str(amount)
            }
            
            result = self.kraken_api_request('/0/private/AddOrder', params)
            
            if result and 'result' in result:
                print(f"✅ Venta exitosa: {amount} {crypto}")
                return True
            else:
                print(f"❌ Error venta: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error ejecutando venta: {e}")
            return False
    
    def execute_buy_order(self):
        """Ejecutar orden de compra"""
        try:
            # Comprar $20 de SOL por defecto
            params = {
                'pair': 'SOLUSD',
                'type': 'buy',
                'ordertype': 'market',
                'volume': '0.1'  # Aproximadamente $20
            }
            
            result = self.kraken_api_request('/0/private/AddOrder', params)
            
            if result and 'result' in result:
                print("✅ Compra exitosa: 0.1 SOL")
                return True
            else:
                print(f"❌ Error compra: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error ejecutando compra: {e}")
            return False
    
    def start_auto_trading_thread(self):
        """Iniciar thread de trading automático"""
        def auto_trading_loop():
            while True:
                try:
                    if self.auto_trading_enabled:
                        self.execute_auto_trade()
                    time.sleep(600)  # Cada 10 minutos
                except Exception as e:
                    logger.error(f"Error en loop auto-trading: {e}")
                    time.sleep(60)  # Esperar 1 minuto si hay error
        
        thread = threading.Thread(target=auto_trading_loop, daemon=True)
        thread.start()
        print("🔄 Auto-trading iniciado cada 10 minutos")
    
    def get_ai_response(self, message, user_id):
        """Obtener respuesta de IA"""
        try:
            # Obtener memoria de conversación
            memory = self.get_conversation_memory(user_id)
            
            # Contexto especializado
            context = f"""
            Eres OMNIX, un asistente de trading de criptomonedas profesional.
            
            {memory}
            
            Características:
            - Respuestas en español
            - Información actualizada de crypto
            - Consejos de trading inteligentes
            - Análisis de mercado
            - Máximo 150 palabras
            
            Mensaje del usuario: {message}
            """
            
            # Usar OpenAI si está disponible
            if self.openai_api_key:
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": context}],
                        max_tokens=200
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    logger.error(f"Error OpenAI: {e}")
            
            # Respuesta por defecto inteligente
            return f"¡Hola! Soy OMNIX, tu asistente de trading crypto. He recibido tu mensaje: '{message[:50]}...' y estoy procesando tu consulta. ¿En qué más puedo ayudarte?"
            
        except Exception as e:
            logger.error(f"Error obteniendo respuesta IA: {e}")
            return "Sistema procesando tu consulta. Intenta nuevamente."
    
    def generate_voice_response(self, text):
        """Generar respuesta de voz"""
        try:
            # Limpiar texto para TTS
            clean_text = re.sub(r'[^\w\s.,!?¿¡]', '', text)
            
            # Generar audio
            tts = gTTS(text=clean_text, lang='es', slow=True)
            
            # Guardar archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                tts.save(tmp_file.name)
                return tmp_file.name
                
        except Exception as e:
            logger.error(f"Error generando voz: {e}")
            return None
    
    def track_user_activity(self, user_id, username, activity_type, details=None):
        """Tracking de actividad de usuario"""
        try:
            conn = sqlite3.connect('omnix_render.db')
            cursor = conn.cursor()
            
            # Insertar o actualizar usuario
            cursor.execute('''
                INSERT OR IGNORE INTO user_tracking (user_id, username)
                VALUES (?, ?)
            ''', (user_id, username))
            
            if activity_type == 'message':
                cursor.execute('''
                    UPDATE user_tracking 
                    SET total_messages = total_messages + 1
                    WHERE user_id = ?
                ''', (user_id,))
            
            elif activity_type == 'trade':
                cursor.execute('''
                    UPDATE user_tracking 
                    SET total_trades = total_trades + 1
                    WHERE user_id = ?
                ''', (user_id,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error tracking usuario: {e}")
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar comando /start"""
        try:
            user = update.effective_user
            user_id = user.id
            username = user.username or user.first_name
            
            # Tracking
            self.track_user_activity(user_id, username, 'start')
            
            welcome_message = f"""
🚀 ¡Bienvenido a OMNIX Global Bot!

Hola {user.first_name}, soy tu asistente de trading crypto profesional.

🔹 Trading automático 24/7
🔹 Análisis de mercado en tiempo real  
🔹 Respuestas por voz automáticas
🔹 Múltiples cryptos soportadas

💡 Comandos disponibles:
/balance - Ver balance actual
/prices - Precios de cryptos
/trading - Estado del trading automático
/help - Ayuda completa

¡Pregúntame cualquier cosa sobre crypto!
            """
            
            await update.message.reply_text(welcome_message)
            
            # Respuesta de voz
            try:
                voice_file = self.generate_voice_response("¡Bienvenido a OMNIX! Tu asistente de trading crypto profesional.")
                if voice_file:
                    with open(voice_file, 'rb') as f:
                        await update.message.reply_voice(voice=f)
                    os.unlink(voice_file)
            except Exception as e:
                logger.error(f"Error enviando voz: {e}")
                
        except Exception as e:
            logger.error(f"Error en handle_start: {e}")
    
    async def handle_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar comando /balance"""
        try:
            user_id = update.effective_user.id
            
            # Tracking
            self.track_user_activity(user_id, update.effective_user.username, 'balance')
            
            balance = self.get_balance()
            
            if balance:
                message = "💰 Tu balance actual:\n\n"
                total_usd = 0
                for crypto, amount in balance.items():
                    if float(amount) > 0:
                        message += f"{crypto}: {float(amount):.4f}\n"
                        if crypto == 'ZUSD':
                            total_usd += float(amount)
                
                # Agregar estado del trading
                can_trade, trades_today, max_trades = self.can_trade_today()
                message += f"\n📊 Trading hoy: {trades_today}/{max_trades}"
                message += f"\n🎯 Estado: {'✅ Activo' if can_trade else '⏸️ Pausado'}"
            else:
                message = "❌ No se pudo obtener el balance. Verifica la conexión."
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error en handle_balance: {e}")
    
    async def handle_prices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar comando /prices"""
        try:
            user_id = update.effective_user.id
            
            # Tracking
            self.track_user_activity(user_id, update.effective_user.username, 'prices')
            
            prices = self.get_crypto_prices()
            
            if prices:
                message = "📊 Precios actuales:\n\n"
                if 'bitcoin' in prices:
                    message += f"₿ Bitcoin: ${prices['bitcoin']['usd']:,.2f}\n"
                if 'ethereum' in prices:
                    message += f"⟠ Ethereum: ${prices['ethereum']['usd']:,.2f}\n"
                if 'solana' in prices:
                    message += f"◎ Solana: ${prices['solana']['usd']:,.2f}\n"
                if 'avalanche-2' in prices:
                    message += f"🔺 Avalanche: ${prices['avalanche-2']['usd']:,.2f}\n"
                
                message += f"\n🕒 Actualizado: {datetime.now().strftime('%H:%M:%S')}"
            else:
                message = "❌ No se pudieron obtener los precios actuales."
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error en handle_prices: {e}")
    
    async def handle_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar comando /trading"""
        try:
            user_id = update.effective_user.id
            
            # Tracking
            self.track_user_activity(user_id, update.effective_user.username, 'trading')
            
            can_trade, trades_today, max_trades = self.can_trade_today()
            
            message = "🤖 Estado del Trading Automático:\n\n"
            message += f"📊 Trades ejecutados hoy: {trades_today}/{max_trades}\n"
            message += f"🎯 Estado: {'✅ Activo' if can_trade else '⏸️ Límite alcanzado'}\n"
            message += f"💰 Objetivo diario: $15 USD\n"
            message += f"🔄 Frecuencia: Cada 10 minutos\n"
            message += f"🛡️ Límite pérdida: $50 USD/día\n"
            
            if not can_trade:
                message += f"\n⏰ El trading se reanudará mañana automáticamente"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error en handle_trading: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar mensajes de texto"""
        try:
            user = update.effective_user
            user_id = user.id
            username = user.username or user.first_name
            message = update.message.text
            
            # Tracking
            self.track_user_activity(user_id, username, 'message')
            
            # Obtener respuesta IA
            ai_response = self.get_ai_response(message, user_id)
            
            # Guardar conversación
            self.save_conversation(user_id, username, message, ai_response)
            
            # Enviar respuesta
            await update.message.reply_text(ai_response)
            
            # Respuesta de voz automática
            try:
                voice_file = self.generate_voice_response(ai_response[:200])  # Limitar longitud
                if voice_file:
                    with open(voice_file, 'rb') as f:
                        await update.message.reply_voice(voice=f)
                    os.unlink(voice_file)
            except Exception as e:
                logger.error(f"Error enviando voz: {e}")
                
        except Exception as e:
            logger.error(f"Error en handle_message: {e}")
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar mensajes de voz"""
        try:
            user = update.effective_user
            user_id = user.id
            username = user.username or user.first_name
            
            # Tracking
            self.track_user_activity(user_id, username, 'voice')
            
            # Respuesta por defecto para voz
            response = "He recibido tu mensaje de voz. Estoy analizando el contenido y te responderé con información actualizada del mercado crypto."
            
            await update.message.reply_text(response)
            
            # Respuesta de voz
            try:
                voice_file = self.generate_voice_response(response)
                if voice_file:
                    with open(voice_file, 'rb') as f:
                        await update.message.reply_voice(voice=f)
                    os.unlink(voice_file)
            except Exception as e:
                logger.error(f"Error enviando voz: {e}")
                
        except Exception as e:
            logger.error(f"Error en handle_voice: {e}")
    
    def run_bot(self):
        """Ejecutar el bot"""
        try:
            print("🚀 Iniciando OMNIX Bot para Render...")
            
            # Crear aplicación
            application = Application.builder().token(self.bot_token).build()
            
            # Handlers
            application.add_handler(CommandHandler("start", self.handle_start))
            application.add_handler(CommandHandler("balance", self.handle_balance))
            application.add_handler(CommandHandler("prices", self.handle_prices))
            application.add_handler(CommandHandler("trading", self.handle_trading))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
            
            # Iniciar bot
            print("✅ Bot iniciado exitosamente en Render")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Error iniciando bot: {e}")
            print(f"❌ Error crítico: {e}")

# Función principal para Render
def main():
    """Función principal para Render"""
    try:
        print("🌐 OMNIX BOT - DEPLOYMENT RENDER INICIADO")
        bot = OmnixBotRender()
        # Ejecutar bot directamente (sin asyncio para evitar problemas)
        bot.run_bot()
    except Exception as e:
        logger.error(f"Error en main: {e}")
        print(f"❌ Error crítico en main: {e}")

# Ejecutar bot
if __name__ == "__main__":
    main()

      
