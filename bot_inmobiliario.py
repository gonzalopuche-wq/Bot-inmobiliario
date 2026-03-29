import requests,logging
from datetime import datetime,timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder,CommandHandler,MessageHandler,ConversationHandler,filters,ContextTypes

BOT_TOKEN="8687228789:AAEloCc64QmIoZt1dKF8dzbNjjt4UHz7
logging.basicConfig(format="%(asctime)s-%(name)s-%(levelname)s-%(message)s",level=logging.INFO)
HON_TIPO,HON_MONTO,HON_MESES,HON_FISCAL=range(4)
ACT_MONTO,ACT_FECHA=range(10,12)
PUN_MONTO,PUN_DIAS=range(20,22)
TASA_IVA=0.21
TASA_DIARIA=0.001
HONORARIOS_INFO={"locacion":{"nombre":"Locación","pide_meses":True,"alicuota":0.05},"compraventa":{"nombre":"Compraventa","pide_meses":False,"alicuota":0.03},"alquiler_comercial":{"nombre":"Locación comercial","pide_meses":True,"alicuota":0.05}}

def fmt_pesos(v):
    return f"$ {v:,.2f}".replace(",","X").replace(".","," ).replace("X",".")

def obtener_icl(d,h):
    url=f"https://api.bcra.gob.ar/estadisticas/v2.0/datosvariable/25/{d}/{h}"
    try:
        r=requests.get(url,timeout=10,verify=False)
        r.raise_for_status()
        return r.json().get("results",[])
    except Exception as e:
        logging.error(f"BCRA:{e}")
        return []

def ultimo_icl():
    hoy=datetime.today()
    datos=obtener_icl((hoy-timedelta(days=30)).strftime("%Y-%m-%d"),hoy.strftime("%Y-%m-%d"))
    return datos[-1] if datos else None

def icl_fecha(fs):
    try:
        f=datetime.strptime(fs,"%d/%m/%Y")
        datos=obtener_icl((f-timedelta(days=5)).strftime("%Y-%m-%d"),(f+timedelta(days=5)).strftime("%Y-%m-%d"))
        if datos:
            fi=f.strftime("%Y-%m-%d")
            for d in reversed(datos):
                if d["fecha"]<=fi:
                    return float(d["valor"])
            return float(datos[0]["valor"])
    except Exception as e:
        logging.error(e)
    return None

async def start(u,c):
    await u.message.reply_text("🏠 *Bot del Corredor Inmobiliario*\n━━━━━━━━━━━━━━━━━━━━\n\n• /honorarios\n• /actualizar\n• /punitorios\n• /ayuda\n\n_Ley 13.154 Santa Fe_",parse_mode="Markdown")

async def ayuda(u,c):
    await u.message.reply_text("📋 *Comandos*\n━━━━━━━━━━━━━━━━━━━━\n\n/honorarios — Calcula honorarios\n/actualizar — Actualiza por ICL\n/punitorios — Interés por mora\n/cancelar — Salir",parse_mode="Markdown")

async def hon_start(u,c):
    await u.message.reply_text("🔢 *Honorarios*\n━━━━━━━━━━━━━━━━━━━━\n\n1️⃣ Locación vivienda\n2️⃣ Compraventa\n3️⃣ Locación comercial\n\nRespondé con el número.",parse_mode="Markdown")
    return HON_TIPO

async def hon_tipo(u,c):
    op=u.message.text.strip()
    t={"1":"locacion","2":"compraventa","3":"alquiler_comercial"}
    if op not in t:
        await u.message.reply_text("Respondé 1, 2 o 3.")
        return HON_TIPO
    c.user_data["ht"]=t[op]
    p="¿Valor mensual del alquiler? (solo número)" if op in("1","3") else "¿Precio de venta? (solo número)"
    await u.message.reply_text(p)
    return HON_MONTO

async def hon_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["hm"]=m
    except:
        await u.message.reply_text("❌ Solo el número. Ej: 250000")
        return HON_MONTO
    if HONORARIOS_INFO[c.user_data["ht"]]["pide_meses"]:
        await u.message.reply_text("📅 ¿Cuántos meses dura el contrato? Ej: 24")
        return HON_MESES
    return await calcular(u,c,m,None)

async def hon_meses(u,c):
    try:
        m=int(u.message.text.strip())
        assert m>0
        c.user_data["hms"]=m
    except:
        await u.message.reply_text("❌ Número positivo. Ej: 24")
        return HON_MESES
    if c.user_data["ht"]=="alquiler_comercial":
        await u.message.reply_text("🧾 Condición fiscal del locador:\n\n1️⃣ Responsable Inscripto\n2️⃣ Monotributista / Exento\n\nRespondé 1 o 2.")
        return HON_FISCAL
    return await calcular(u,c,c.user_data["hm"],m)

async def hon_fiscal(u,c):
    op=u.message.text.strip()
    if op not in("1","2"):
        await u.message.reply_text("Respondé 1 o 2.")
        return HON_FISCAL
    c.user_data["hf"]=op
    return await calcular(u,c,c.user_data["hm"],c.user_data["hms"])

async def calcular(u,c,monto,meses):
    tk=c.user_data["ht"]
    ti=HONORARIOS_INFO[tk]
    al=ti["alicuota"]
    bs=""
    if meses:
        base=monto*meses
        hn=base*al
        iv=hn*TASA_IVA
        ht=hn+iv
        det=f"📋 Alquiler: {fmt_pesos(monto)}\n✖️ Meses: {meses}\n📦 Base: {fmt_pesos(base)}\n✖️ Alícuota: {al*100:.0f}%\n\n"
        if tk=="alquiler_comercial":
            fis=c.user_data.get("hf","2")
            if fis=="1":
                bc=monto*(1+TASA_IVA)*meses
                cond="Responsable Inscripto (alquiler+IVA)"
            else:
                bc=monto*meses
                cond="Monotributista/Exento"
            sel=bc*0.025
            bs=f"━━━━━━━━━━━━━━━━━━━━\n🔏 *Sellado 2,5%*\n_{cond}_\nBase: {fmt_pesos(bc)}\nSellado: *{fmt_pesos(sel)}*\n\n💵 *Total+sellado: {fmt_pesos(ht+sel)}*\n\n"
    else:
        hn=monto*al
        iv=hn*TASA_IVA
        ht=hn+iv
        det=f"📦 Precio venta: {fmt_pesos(monto)}\n✖️ Alícuota: {al*100:.0f}%\n\n"
    txt=(f"✅ *{ti['nombre']}*\n━━━━━━━━━━━━━━━━━━━━\n\n{det}"
         f"💰 Honorarios netos: *{fmt_pesos(hn)}*\n🧾 IVA 21%: {fmt_pesos(iv)}\n━━━━━━━━━━━━━━━━━━━━\n"
         f"💵 *Con IVA: {fmt_pesos(ht)}*\n\n{bs}_Arancel MPP — Ley 13.154_")
    await u.message.reply_text(txt,parse_mode="Markdown")
    return ConversationHandler.END

async def act_start(u,c):
    await u.message.reply_text("📈 *Actualización ICL*\n\n¿Alquiler actual? (solo número)",parse_mode="Markdown")
    return ACT_MONTO

async def act_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["am"]=m
    except:
        await u.message.reply_text("❌ Solo el número.")
        return ACT_MONTO
    await u.message.reply_text("📅 Fecha del último ajuste (DD/MM/AAAA)")
    return ACT_FECHA

async def act_fecha(u,c):
    fs=u.message.text.strip()
    try:
        datetime.strptime(fs,"%d/%m/%Y")
    except:
        await u.message.reply_text("❌ Formato DD/MM/AAAA")
        return ACT_FECHA
    await u.message.reply_text("⏳ Consultando BCRA...")
    m=c.user_data["am"]
    i0=icl_fecha(fs)
    ih=ultimo_icl()
    if not i0 or not ih:
        await u.message.reply_text("❌ Error BCRA. Intentá más tarde.")
        return ConversationHandler.END
    iv=float(ih["valor"])
    var=(iv/i0)-1
    nm=m*(iv/i0)
    await u.message.reply_text(f"✅ *Actualización ICL*\n━━━━━━━━━━━━━━━━━━━━\n\n📅 Inicio: {fs}\n📅 Actual: {ih['fecha']}\n\n📈 Variación: *{var*100:.2f}%*\n\n💰 Anterior: {fmt_pesos(m)}\n━━━━━━━━━━━━━━━━━━━━\n🏠 *Nuevo: {fmt_pesos(nm)}*\n\n_BCRA — ICL Ley 27.551_",parse_mode="Markdown")
    return ConversationHandler.END

async def pun_start(u,c):
    await u.message.reply_text(f"⚠️ *Punitorios*\nTasa: {TASA_DIARIA*100:.1f}% diario\n\n¿Monto adeudado?",parse_mode="Markdown")
    return PUN_MONTO

async def pun_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["pm"]=m
    except:
        await u.message.reply_text("❌ Solo el número.")
        return PUN_MONTO
    await u.message.reply_text("📅 ¿Cuántos días de mora?")
    return PUN_DIAS

async def pun_dias(u,c):
    try:
        d=int(u.message.text.strip())
        assert d>0
    except:
        await u.message.reply_text("❌ Número positivo.")
        return PUN_DIAS
    m=c.user_data["pm"]
    i=m*TASA_DIARIA*d
    await u.message.reply_text(f"✅ *Punitorios*\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Monto: {fmt_pesos(m)}\n📅 Días: {d}\n\n⚠️ Interés: *{fmt_pesos(i)}*\n━━━━━━━━━━━━━━━━━━━━\n💵 *Total: {fmt_pesos(m+i)}*",parse_mode="Markdown")
    return ConversationHandler.END

async def cancelar(u,c):
    await u.message.reply_text("❌ Cancelado. /ayuda para ver opciones.")
    return ConversationHandler.END

async def desconocido(u,c):
    await u.message.reply_text("Escribí /ayuda para ver los comandos.")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    ch=ConversationHandler(entry_points=[CommandHandler("honorarios",hon_start)],states={HON_TIPO:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_tipo)],HON_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_monto)],HON_MESES:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_meses)],HON_FISCAL:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_fiscal)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    ca=ConversationHandler(entry_points=[CommandHandler("actualizar",act_start)],states={ACT_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,act_monto)],ACT_FECHA:[MessageHandler(filters.TEXT&~filters.COMMAND,act_fecha)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    cp=ConversationHandler(entry_points=[CommandHandler("punitorios",pun_start)],states={PUN_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_monto)],PUN_DIAS:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_dias)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("ayuda",ayuda))
    app.add_handler(ch)
    app.add_handler(ca)
    app.add_handler(cp)
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,desconocido))
    print("✅ Bot corriendo...")
    app.run_polling()

if __name__=="__main__":
    main()
