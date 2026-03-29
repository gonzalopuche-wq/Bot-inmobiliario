import requests
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN = "8687228789:AAFQJdFXhSRQ-0o79NWphNxA4PCkcM1759s"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

HON_TIPO, HON_MONTO, HON_MESES, HON_FISCAL = range(4)
ACT_MONTO, ACT_FECHA = range(10, 12)
PUN_MONTO, PUN_DIAS = range(20, 22)

def fmt_pesos(valor: float) -> str:
    return f"$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def obtener_icl(fecha_desde, fecha_hasta):
    url = f"https://api.bcra.gob.ar/estadisticas/v2.0/datosvariable/25/{fecha_desde}/{fecha_hasta}"
    try:
        r = requests.get(url, timeout=10, verify=False)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        logging.error(f"Error BCRA: {e}")
        return []

def ultimo_icl_disponible():
    hoy = datetime.today()
    desde = (hoy - timedelta(days=30)).strftime("%Y-%m-%d")
    hasta = hoy.strftime("%Y-%m-%d")
    datos = obtener_icl(desde, hasta)
    return datos[-1] if datos else None

def icl_en_fecha(fecha_str):
    try:
        fecha = datetime.strptime(fecha_str, "%d/%m/%Y")
        desde = (fecha - timedelta(days=5)).strftime("%Y-%m-%d")
        hasta = (fecha + timedelta(days=5)).strftime("%Y-%m-%d")
        datos = obtener_icl(desde, hasta)
        if datos:
            fecha_iso = fecha.strftime("%Y-%m-%d")
            for d in reversed(datos):
                if d["fecha"] <= fecha_iso:
                    return float(d["valor"])
            return float(datos[0]["valor"])
    except Exception as e:
        logging.error(f"Error ICL fecha: {e}")
    return None
HONORARIOS_INFO = {
    "locacion": {
        "nombre": "Locación",
        "pide_meses": True,
        "alicuota": 0.05,
    },
    "compraventa": {
        "nombre": "Compraventa",
        "pide_meses": False,
        "alicuota": 0.03,
    },
    "alquiler_comercial": {
        "nombre": "Locación comercial",
        "pide_meses": True,
        "alicuota": 0.05,
    },
}

TASA_IVA = 0.21
TASA_DIARIA = 0.001

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🏠 *Bot del Corredor Inmobiliario*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Calculadoras profesionales al instante.\n\n"
        "📌 *Comandos disponibles:*\n"
        "• /honorarios — Calcula honorarios\n"
        "• /actualizar — Actualiza alquiler por ICL\n"
        "• /punitorios — Interés por mora\n"
        "• /ayuda — Ver todos los comandos\n\n"
        "_Basado en Ley Provincial N.º 13.154 (Santa Fe)_"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "📋 *Comandos disponibles*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔢 */honorarios*\n"
        "Calcula honorarios por tipo de operación\n\n"
        "📈 */actualizar*\n"
        "Actualiza alquiler por ICL (BCRA)\n\n"
        "⚠️ */punitorios*\n"
        "Calcula interés por mora\n\n"
        "Escribí /cancelar para salir en cualquier momento."
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def honorarios_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🔢 *Calculadora de Honorarios*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "¿Qué tipo de operación?\n\n"
        "1️⃣ Locación (vivienda)\n"
        "2️⃣ Compraventa\n"
        "3️⃣ Locación comercial\n\n"
        "Respondé con el número."
    )
    await update.message.reply_text(texto, parse_mode="Markdown")
    return HON_TIPO

async def honorarios_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opcion = update.message.text.strip()
    tipos = {"1": "locacion", "2": "compraventa", "3": "alquiler_comercial"}
    if opcion not in tipos:
        await update.message.reply_text("Respondé con 1, 2 o 3.")
        return HON_TIPO
    context.user_data["hon_tipo"] = tipos[opcion]
    if opcion in ("1", "3"):
        pregunta = "¿Cuál es el *valor mensual del alquiler* pactado? (solo el número)"
    else:
        pregunta = "¿Cuál es el *precio de venta*? (solo el número)"
    await update.message.reply_text(pregunta, parse_mode="Markdown")
    return HON_MONTO

async def honorarios_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        texto_limpio = update.message.text.strip().replace(".", "").replace(",", ".")
        monto = float(texto_limpio)
        context.user_data["hon_monto"] = monto
    except ValueError:
        await update.message.reply_text("❌ Ingresá solo el número. Ej: 250000")
        return HON_MONTO
    tipo_key = context.user_data["hon_tipo"]
    tipo_info = HONORARIOS_INFO[tipo_key]
    if tipo_info["pide_meses"]:
        await update.message.reply_text(
            "📅 ¿Cuántos *meses dura el contrato*?\nEj: 24",
            parse_mode="Markdown"
        )
        return HON_MESES
    else:
        return await _calcular_honorarios

  async def honorarios_meses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        meses = int(update.message.text.strip())
        if meses <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Ingresá un número entero. Ej: 24")
        return HON_MESES
    context.user_data["hon_meses"] = meses
    if context.user_data["hon_tipo"] == "alquiler_comercial":
        await update.message.reply_text(
            "🧾 ¿Condición fiscal del locador?\n\n"
            "1️⃣ Responsable Inscripto\n"
            "2️⃣ Monotributista / Exento\n\n"
            "Respondé con el número.",
            parse_mode="Markdown"
        )
        return HON_FISCAL
    monto = context.user_data["hon_monto"]
    return await _calcular_honorarios(update, context, monto, meses)

async def honorarios_fiscal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opcion = update.message.text.strip()
    if opcion not in ("1", "2"):
        await update.message.reply_text("Respondé con 1 o 2.")
        return HON_FISCAL
    context.user_data["hon_fiscal"] = opcion
    monto = context.user_data["hon_monto"]
    meses = context.user_data["hon_meses"]
    return await _calcular_honorarios(update, context, monto, meses)

async def _calcular_honorarios(update, context, monto, meses):
    tipo_key = context.user_data["hon_tipo"]
    tipo_info = HONORARIOS_INFO[tipo_key]
    alicuota = tipo_info["alicuota"]
    if meses:
        base = monto * meses
        honorarios_neto = base * alicuota
        iva = honorarios_neto * TASA_IVA
        honorarios_total = honorarios_neto + iva
        detalle = (
            f"📋 Alquiler inicial: {fmt_pesos(monto)}\n"
            f"✖️ Meses: {meses}\n"
            f"📦 Base contrato: {fmt_pesos(base)}\n"
            f"✖️ Alícuota: {alicuota * 100:.0f}%\n\n"
        )
        if tipo_key == "alquiler_comercial":
            fiscal = context.user_data.get("hon_fiscal", "2")
            if fiscal == "1":
                alquiler_con_iva = monto * (1 + TASA_IVA)
                base_sellado = alquiler_con_iva * meses
                condicion = "Responsable Inscripto (alquiler + IVA)"
            else:
                alquiler_con_iva = monto
                base_sellado = monto * meses
                condicion = "Monotributista / Exento"
            sellado = base_sellado * 0.025
            bloque_sellado = (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔏 *Sellado (2,5%)*\n"
                f"Condición: _{condicion}_\n"
                f"Base sellado: {fmt_pesos(base_sellado)}\n"
                f"Sellado: *{fmt_pesos(sellado)}*\n\n"
                f"💵 *Total honor. + sellado: {fmt_pesos(honorarios_total + sellado)}*\n\n"
            )
        else:
            bloque_sellado = ""
    else:
        honorarios_neto = monto * alicuota
        iva = honorarios_neto * TASA_IVA
        honorarios_total = honorarios_neto + iva
        detalle = (
            f"📦 Precio de venta: {fmt_pesos(monto)}\n"
            f"✖️ Alícuota: {alicuota * 100:.0f}%\n\n"
        )
        bloque_sellado = ""
    texto = (
        f"✅ *Resultado — {tipo_info['nombre']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{detalle}"
        f"💰 Honorarios netos: *{fmt_pesos(honorarios_neto)}*\n"
        f"🧾 IVA (21%): {fmt_pesos(iva)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Honorarios con IVA: {fmt_pesos(honorarios_total)}*\n\n"
        f"{bloque_sellado}"
        f"_Arancel MPP — Ley 13.154 (Santa Fe)_"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")
    return ConversationHandler.END

async def actualizar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 *Actualización por ICL*\n\n¿Cuál es el alquiler actual? (solo el número)",
        parse_mode="Markdown"
    )
    return ACT_MONTO

async def actualizar_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        monto = float(update.message.text.strip().replace(".", "").replace(",", "."))
        context.user_data["act_monto"] = monto
    except ValueError:
        await update.message.reply_text("❌ Solo el número. Ej: 180000")
        return ACT_MONTO
    await update.message.reply_text(
        "📅 ¿Fecha del último ajuste?\nFormato: DD/MM/AAAA",
        parse_mode="Markdown"
    )
    return ACT_FECHA

async def actualizar_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fecha_str = update.message.text.strip()
    try:
        datetime.strptime(fecha_str, "%d/%m/%Y")
    except ValueError:
        await update.message.reply_text("❌ Formato incorrecto. Usá DD/MM/AAAA")
        return ACT_FECHA
    await update.message.reply_text("⏳ Consultando BCRA...")
    monto = context.user_data["act_monto"]
    icl_entonces = icl_en_fecha(fecha_str)
    icl_hoy_data = ultimo_icl_disponible()
    if not icl_entonces or not icl_hoy_data:
        await update.message.reply_text("❌ No pude obtener datos del BCRA. Intentá más tarde.")
        return ConversationHandler.END
    icl_hoy = float(icl_hoy_data["valor"])
    variacion = (icl_hoy / icl_entonces) - 1
    nuevo_monto = monto * (icl_hoy / icl_entonces)
    texto = (
        f"✅ *Resultado — Actualización ICL*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Fecha inicio: {fecha_str}\n"
        f"📅 Fecha actual: {icl_hoy_data['fecha']}\n\n"
        f"📈 Variación: *{variacion * 100:.2f}%*\n\n"
        f"💰 Alquiler anterior: {fmt_pesos(monto)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏠 *Nuevo alquiler: {fmt_pesos(nuevo_monto)}*\n\n"
        f"_Fuente: BCRA — ICL (Ley 27.551)_"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")
    return ConversationHandler.END

async def punitorios_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚠️ *Punitorios*\n\nTasa: {TASA_DIARIA*100:.1f}% diario\n\n¿Monto adeudado?",
        parse_mode="Markdown"
    )
    return PUN_MONTO

async def punitorios_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        monto = float(update.message.text.strip().replace(".", "").replace(",", "."))
        context.user_data["pun_monto"] = monto
    except ValueError:
        await update.message.reply_text("❌ Solo el número. Ej: 150000")
        return PUN_MONTO
    await update.message.reply_text("📅 ¿Cuántos días de mora?")
    return PUN_DIAS

async def punitorios_dias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dias = int(update.message.text.strip())
        if dias <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Ingresá un número positivo. Ej: 15")
        return PUN_DIAS
    monto = context.user_data["pun_monto"]
    interes = monto * TASA_DIARIA * dias
    total = monto + interes
    texto = (
        f"✅ *Resultado — Punitorios*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Monto: {fmt_pesos(monto)}\n"
        f"📅 Días: {dias}\n\n"
        f"⚠️ Punitorios: *{fmt_pesos(interes)}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Total: {fmt_pesos(total)}*"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelado. Escribí /ayuda para ver opciones.")
    return ConversationHandler.END

async def mensaje_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Escribí /ayuda para ver los comandos disponibles.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv_honorarios = ConversationHandler(
        entry_points=[CommandHandler("honorarios", honorarios_start)],
        states={
            HON_TIPO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, honorarios_tipo)],
            HON_MONTO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, honorarios_monto)],
            HON_MESES:  [MessageHandler(filters.TEXT & ~filters.COMMAND, honorarios_meses)],
            HON_FISCAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, honorarios_fiscal)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
    conv_actualizar = ConversationHandler(
        entry_points=[CommandHandler("actualizar", actualizar_start)],
        states={
            ACT_MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, actualizar_monto)],
            ACT_FECHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, actualizar_fecha)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
    conv_punitorios = ConversationHandler(
        entry_points=[CommandHandler("punitorios", punitorios_start)],
        states={
            PUN_MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, punitorios_monto)],
            PUN_DIAS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, punitorios_dias)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(conv_honorarios)
    app.add_handler(conv_actualizar)
    app.add_handler(conv_punitorios)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_desconocido))
    print("✅ Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
      
