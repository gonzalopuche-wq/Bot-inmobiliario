import requests,logging,re,urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime,timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder,CommandHandler,MessageHandler,ConversationHandler,filters,ContextTypes

BOT_TOKEN="8687228789:AAEloCc64QmIoZt1dKF8dzbNjjt4UHz7swI"
logging.basicConfig(format="%(asctime)s-%(name)s-%(levelname)s-%(message)s",level=logging.INFO)
HON_CAT,HON_SUBTIPO,HON_MONTO,HON_MESES,HON_FISCAL=range(5)
ACT_PERIODO,ACT_INDICE,ACT_MONTO,ACT_PORC=range(9,13)
PUN_TASA,PUN_MONTO,PUN_DIAS=range(20,23)
TASA_IVA=0.21
VENTA={"1":{"n":"Casas/Dptos/Oficinas/Locales/Galpones/Quintas","c":0.03,"p":0.03},"2":{"n":"Terrenos/Lotes/Nichos","c":0.10,"p":0.10},"3":{"n":"Edificios PH","c":0.03,"p":0.03},"4":{"n":"Consorcios/Fideicomisos","c":0.03,"p":0.05},"5":{"n":"Fondo de Comercio","c":0.05,"p":0.05},"6":{"n":"Campos","c":0.03,"p":0.03}}
ALQUILER={"1":{"n":"Vivienda","al":0.05,"fiscal":False,"sellado":False},"2":{"n":"Locación comercial","al":0.05,"fiscal":True,"sellado":True}}
PERIODOS={"1":"Mensual","2":"Trimestral","3":"Cuatrimestral","4":"Semestral","5":"Anual"}
INDICES_NOMBRE={"1":"ICL","2":"IPC","3":"CVS","4":"Otro"}

def fmt(v):
    return f"$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def obtener_jus():
    try:
        r=requests.get("https://www.cajaforense.com/index.php?action=portal/show&id_section=148&mnuId_parent=2",timeout=10,verify=False)
        m=re.search(r'JUS ARANCELARIA[^$]*\$([0-9.,]+)',r.text)
        if m: return float(m.group(1).replace(".","").replace(",","."))
    except Exception as e: logging.error(f"JUS:{e}")
    return 124873.05

async def start(u,c):
    await u.message.reply_text("🏠 *Bot del Corredor Inmobiliario*\n━━━━━━━━━━━━━━━━━━━━\n\n• /honorarios — Calculadora COCIR\n• /actualizar — Actualización de alquiler\n• /punitorios — Interés por mora\n• /ayuda\n\n_Ley 13.154 Santa Fe_",parse_mode="Markdown")

async def ayuda(u,c):
    await u.message.reply_text("📋 *Comandos*\n━━━━━━━━━━━━━━━━━━━━\n\n/honorarios — Honorarios COCIR\n/actualizar — Actualiza alquiler por índice\n/punitorios — Interés por mora\n/cancelar — Salir",parse_mode="Markdown")

async def hon_start(u,c):
    await u.message.reply_text("🔢 *Honorarios COCIR*\n━━━━━━━━━━━━━━━━━━━━\n\n1️⃣ Venta\n2️⃣ Alquiler\n3️⃣ Tasación\n4️⃣ Administración\n\nRespondé con el número.",parse_mode="Markdown")
    return HON_CAT

async def hon_cat(u,c):
    op=u.message.text.strip()
    if op not in("1","2","3","4"):
        await u.message.reply_text("Respondé 1, 2, 3 o 4.")
        return HON_CAT
    c.user_data["hcat"]=op
    if op=="1":
        await u.message.reply_text("🏢 *Venta — Tipo de inmueble*\n━━━━━━━━━━━━━━━━━━━━\n\n1️⃣ Casas/Dptos/Oficinas/Locales/Galpones/Quintas\n2️⃣ Terrenos/Lotes/Nichos\n3️⃣ Edificios PH\n4️⃣ Consorcios/Fideicomisos\n5️⃣ Fondo de Comercio\n6️⃣ Campos\n\nRespondé con el número.",parse_mode="Markdown")
        return HON_SUBTIPO
    elif op=="2":
        await u.message.reply_text("🏠 *Alquiler — Tipo*\n━━━━━━━━━━━━━━━━━━━━\n\n1️⃣ Vivienda\n2️⃣ Locación comercial\n\nRespondé con el número.",parse_mode="Markdown")
        return HON_SUBTIPO
    elif op=="3":
        await u.message.reply_text("📐 *Tasación*\n\n¿Cuál es el valor tasado? (solo el número)",parse_mode="Markdown")
        return HON_MONTO
    else:
        await u.message.reply_text("🏢 *Administración*\n\n¿Monto mensual de alquiler cobrado? (solo el número)",parse_mode="Markdown")
        return HON_MONTO

async def hon_subtipo(u,c):
    op=u.message.text.strip()
    cat=c.user_data["hcat"]
    if cat=="1" and op not in VENTA:
        await u.message.reply_text("Respondé del 1 al 6.")
        return HON_SUBTIPO
    if cat=="2" and op not in ALQUILER:
        await u.message.reply_text("Respondé 1 o 2.")
        return HON_SUBTIPO
    c.user_data["hsub"]=op
    p="💰 ¿Precio de venta? (solo el número)" if cat=="1" else "💰 ¿Valor mensual del alquiler? (solo el número)"
    await u.message.reply_text(p)
    return HON_MONTO

async def hon_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["hmonto"]=m
    except:
        await u.message.reply_text("❌ Solo el número. Ej: 5000000")
        return HON_MONTO
    cat=c.user_data["hcat"]
    if cat in("1","3","4"): return await calcular(u,c,m,None)
    await u.message.reply_text("📅 ¿Cuántos meses dura el contrato? Ej: 24")
    return HON_MESES

async def hon_meses(u,c):
    try:
        m=int(u.message.text.strip())
        assert m>0
        c.user_data["hmeses"]=m
    except:
        await u.message.reply_text("❌ Número positivo. Ej: 24")
        return HON_MESES
    sub=c.user_data["hsub"]
    if ALQUILER[sub]["fiscal"]:
        await u.message.reply_text("🧾 Condición fiscal del locador:\n\n1️⃣ Responsable Inscripto\n2️⃣ Monotributista / Exento\n\nRespondé 1 o 2.")
        return HON_FISCAL
    return await calcular(u,c,c.user_data["hmonto"],m)

async def hon_fiscal(u,c):
    op=u.message.text.strip()
    if op not in("1","2"):
        await u.message.reply_text("Respondé 1 o 2.")
        return HON_FISCAL
    c.user_data["hfiscal"]=op
    return await calcular(u,c,c.user_data["hmonto"],c.user_data["hmeses"])

async def calcular(u,c,monto,meses):
    cat=c.user_data["hcat"]
    if cat=="3":
        jus=obtener_jus()
        hon=monto*0.001
        txt=(f"✅ *Tasación*\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Valor tasado: {fmt(monto)}\n📐 Alícuota: 1‰\n💵 Honorario: *{fmt(hon)}*\n\n━━━━━━━━━━━━━━━━━━━━\n📌 *Mínimos en JUS* (1 JUS = {fmt(jus)})\n• Informativa vivienda: *{fmt(jus)}* (1 JUS)\n• Técnica vivienda: *{fmt(jus*2)}* (2 JUS)\n• Industrias/campos/f.comercio: *{fmt(jus*4)}* (4 JUS)\n\n_Caja Forense 2° Circ. · COCIR_")
        await u.message.reply_text(txt,parse_mode="Markdown")
        return ConversationHandler.END
    if cat=="4":
        hon=monto*0.10
        iva=hon*TASA_IVA
        txt=(f"✅ *Administración*\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Alquiler cobrado: {fmt(monto)}\n📐 Alícuota: 10%\n\n💵 Honorario neto: *{fmt(hon)}*\n🧾 IVA 21%: {fmt(iva)}\n━━━━━━━━━━━━━━━━━━━━\n💵 *Total con IVA: {fmt(hon+iva)}*\n\n_COCIR — Ley 13.154_")
        await u.message.reply_text(txt,parse_mode="Markdown")
        return ConversationHandler.END
    if cat=="1":
        sub=c.user_data["hsub"]
        info=VENTA[sub]
        hc=monto*info["c"]
        hp=monto*info["p"]
        txt=(f"✅ *Venta — {info['n']}*\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Precio: {fmt(monto)}\n\n👤 *Comprador ({info['c']*100:.0f}%)*\n   Neto: {fmt(hc)} · IVA: {fmt(hc*TASA_IVA)}\n   *Total: {fmt(hc*1.21)}*\n\n🏠 *Propietario ({info['p']*100:.0f}%)*\n   Neto: {fmt(hp)} · IVA: {fmt(hp*TASA_IVA)}\n   *Total: {fmt(hp*1.21)}*\n\n━━━━━━━━━━━━━━━━━━━━\n💵 *Total ambas partes: {fmt(hc*1.21+hp*1.21)}*\n\n_COCIR — Ley 13.154_")
        await u.message.reply_text(txt,parse_mode="Markdown")
        return ConversationHandler.END
    sub=c.user_data["hsub"]
    info=ALQUILER[sub]
    base=monto*meses
    hl=base*info["al"]
    hd=base*info["al"]
    sel_bloque=""
    if info["sellado"]:
        fis=c.user_data.get("hfiscal","2")
        bs=monto*(1+TASA_IVA)*meses if fis=="1" else base
        cond="Resp. Inscripto (alquiler+IVA)" if fis=="1" else "Monotributista/Exento"
        sel=bs*0.025
        sel_bloque=f"━━━━━━━━━━━━━━━━━━━━\n🔏 *Sellado 2,5%* _{cond}_\nBase: {fmt(bs)}\n*Sellado: {fmt(sel)}*\n\n"
    txt=(f"✅ *Alquiler — {info['n']}*\n━━━━━━━━━━━━━━━━━━━━\n\n💰 {fmt(monto)} × {meses} meses\n📦 Base: {fmt(base)} · Alícuota: {info['al']*100:.0f}%\n\n👤 *Locatario*\n   Neto: {fmt(hl)} · IVA: {fmt(hl*TASA_IVA)}\n   *Total: {fmt(hl*1.21)}*\n\n🏠 *Locador*\n   Neto: {fmt(hd)} · IVA: {fmt(hd*TASA_IVA)}\n   *Total: {fmt(hd*1.21)}*\n\n{sel_bloque}_COCIR — Ley 13.154_")
    await u.message.reply_text(txt,parse_mode="Markdown")
    return ConversationHandler.END

async def act_start(u,c):
    await u.message.reply_text("📈 *Actualización de Alquiler*\n━━━━━━━━━━━━━━━━━━━━\n\n¿Cada cuánto se actualiza?\n\n1️⃣ Mensual\n2️⃣ Trimestral\n3️⃣ Cuatrimestral\n4️⃣ Semestral\n5️⃣ Anual\n\nRespondé con el número.",parse_mode="Markdown")
    return ACT_PERIODO

async def act_periodo(u,c):
    op=u.message.text.strip()
    if op not in PERIODOS:
        await u.message.reply_text("Respondé del 1 al 5.")
        return ACT_PERIODO
    c.user_data["aperido"]=op
    await u.message.reply_text(f"📊 Período: *{PERIODOS[op]}*\n\n¿Qué índice usás?\n\n1️⃣ ICL\n2️⃣ IPC\n3️⃣ CVS\n4️⃣ Otro\n\nRespondé con el número.",parse_mode="Markdown")
    return ACT_INDICE

async def act_indice(u,c):
    op=u.message.text.strip()
    if op not in INDICES_NOMBRE:
        await u.message.reply_text("Respondé del 1 al 4.")
        return ACT_INDICE
    c.user_data["aindice"]=op
    await u.message.reply_text(f"💰 ¿Alquiler actual? (solo el número)")
    return ACT_MONTO

async def act_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["am"]=m
    except:
        await u.message.reply_text("❌ Solo el número.")
        return ACT_MONTO
    ind=INDICES_NOMBRE[c.user_data["aindice"]]
    per=PERIODOS[c.user_data["aperido"]]
    await u.message.reply_text(f"📐 ¿Cuál es el porcentaje de variación {ind} del período {per}?\n\nEj: `84.5` para 84,5%\n_(lo consultás en bcra.gob.ar o cocir.org.ar)_",parse_mode="Markdown")
    return ACT_PORC

async def act_porc(u,c):
    try:
        p=float(u.message.text.strip().replace(",","."))
        assert p>0
    except:
        await u.message.reply_text("❌ Ingresá el porcentaje. Ej: 84.5")
        return ACT_PORC
    m=c.user_data["am"]
    ind=INDICES_NOMBRE[c.user_data["aindice"]]
    per=PERIODOS[c.user_data["aperido"]]
    nm=m*(1+p/100)
    inc=nm-m
    await u.message.reply_text(
        f"✅ *Actualización — {ind} {per}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Índice: {ind}\n"
        f"🗓 Período: {per}\n"
        f"📈 Variación: *{p:.2f}%*\n\n"
        f"💰 Alquiler anterior: {fmt(m)}\n"
        f"➕ Incremento: {fmt(inc)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏠 *Nuevo alquiler: {fmt(nm)}*",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def pun_start(u,c):
    await u.message.reply_text("⚠️ *Punitorios*\n━━━━━━━━━━━━━━━━━━━━\n\n📐 ¿Cuál es la *tasa diaria* del contrato?\n\nEj: `0.1` → 0,1% diario (~3% mensual)\nEj: `0.5` → 0,5% diario (~15% mensual)",parse_mode="Markdown")
    return PUN_TASA

async def pun_tasa(u,c):
    try:
        t=float(u.message.text.strip().replace(",","."))
        assert 0<t<100
        c.user_data["ptasa"]=t/100
    except:
        await u.message.reply_text("❌ Ingresá un número. Ej: 0.1")
        return PUN_TASA
    await u.message.reply_text(f"✅ Tasa: {t:.2f}% diario\n\n💰 ¿Monto adeudado? (solo el número)")
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
    tasa=c.user_data["ptasa"]
    i=m*tasa*d
    await u.message.reply_text(f"✅ *Punitorios*\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Monto: {fmt(m)}\n📐 Tasa: {tasa*100:.2f}% diario\n📅 Días: {d}\n\n⚠️ Interés: *{fmt(i)}*\n━━━━━━━━━━━━━━━━━━━━\n💵 *Total: {fmt(m+i)}*",parse_mode="Markdown")
    return ConversationHandler.END

async def cancelar(u,c):
    await u.message.reply_text("❌ Cancelado. /ayuda para ver opciones.")
    return ConversationHandler.END

async def desconocido(u,c):
    await u.message.reply_text("Escribí /ayuda para ver los comandos.")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    ch=ConversationHandler(entry_points=[CommandHandler("honorarios",hon_start)],states={HON_CAT:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_cat)],HON_SUBTIPO:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_subtipo)],HON_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_monto)],HON_MESES:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_meses)],HON_FISCAL:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_fiscal)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    ca=ConversationHandler(entry_points=[CommandHandler("actualizar",act_start)],states={ACT_PERIODO:[MessageHandler(filters.TEXT&~filters.COMMAND,act_periodo)],ACT_INDICE:[MessageHandler(filters.TEXT&~filters.COMMAND,act_indice)],ACT_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,act_monto)],ACT_PORC:[MessageHandler(filters.TEXT&~filters.COMMAND,act_porc)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    cp=ConversationHandler(entry_points=[CommandHandler("punitorios",pun_start)],states={PUN_TASA:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_tasa)],PUN_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_monto)],PUN_DIAS:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_dias)]},fallbacks=[CommandHandler("cancelar",cancelar)])
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
