import requests,logging,re,urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime,timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder,CommandHandler,MessageHandler,ConversationHandler,filters,ContextTypes

BOT_TOKEN="8687228789:AAEloCc64QmIoZt1dKF8dzbNjjt4UHz7swI"
logging.basicConfig(format="%(asctime)s-%(name)s-%(levelname)s-%(message)s",level=logging.INFO)
HON_CAT,HON_SUBTIPO,HON_TAS_TIPO,HON_MONEDA,HON_MONTO,HON_MESES,HON_FISCAL=range(7)
ACT_PERIODO,ACT_INDICE,ACT_MONTO,ACT_FECHA=range(9,13)
PUN_TASA,PUN_MONTO,PUN_DIAS=range(20,23)
TASA_IVA=0.21
VENTA={"1":{"n":"Casas/Dptos/Oficinas/Locales/Galpones/Quintas","c":0.03,"p":0.03},"2":{"n":"Terrenos/Lotes/Nichos","c":0.10,"p":0.10},"3":{"n":"Edificios PH","c":0.03,"p":0.03},"4":{"n":"Consorcios/Fideicomisos","c":0.03,"p":0.05},"5":{"n":"Fondo de Comercio","c":0.05,"p":0.05},"6":{"n":"Campos","c":0.03,"p":0.03}}
ALQUILER={"1":{"n":"Vivienda","al":0.05,"fiscal":False,"sellado":False},"2":{"n":"Locacion comercial","al":0.05,"fiscal":True,"sellado":True}}
PERIODOS={"1":"Mensual","2":"Trimestral","3":"Cuatrimestral","4":"Semestral","5":"Anual"}
INDICES={"1":{"n":"ICL","k":"icl"},"2":{"n":"IPC","k":"ipc"},"3":{"n":"Casa Propia","k":"casapropia"},"4":{"n":"UVA","k":"uva"}}
TIPOS_TAS={"1":{"n":"Informativa vivienda","jus":1},"2":{"n":"Tecnica vivienda","jus":2},"3":{"n":"Industrias/campos/f.comercio","jus":4}}
BASE="https://api.argly.com.ar/api"

def fmt(v):
    return f"$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def fmt_usd(v):
    return f"USD {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def obtener_jus():
    try:
        r=requests.get("https://www.cajaforense.com/index.php?action=portal/show&id_section=148&mnuId_parent=2",timeout=10,verify=False)
        m=re.search(r'JUS ARANCELARIA[^$]*\$([0-9.,]+)',r.text)
        if m: return float(m.group(1).replace(".","").replace(",","."))
    except Exception as e: logging.error(f"JUS:{e}")
    return 124873.05

def obtener_blue():
    try:
        r=requests.get(f"{BASE}/dolar",timeout=10)
        r.raise_for_status()
        data=r.json()
        logging.info(f"BLUE raw: {str(data)[:300]}")
        if isinstance(data,list):
            for d in data:
                nombre=str(d.get("nombre","")).lower()
                if "blue" in nombre:
                    compra=float(d.get("compra",0))
                    venta=float(d.get("venta",0))
                    if compra and venta:
                        return (compra+venta)/2
        if isinstance(data,dict):
            for k,v in data.items():
                if "blue" in str(k).lower():
                    if isinstance(v,dict):
                        compra=float(v.get("compra",0))
                        venta=float(v.get("venta",0))
                        if compra and venta: return (compra+venta)/2
    except Exception as e: logging.error(f"BLUE:{e}")
    return None

def get_historico(k):
    try:
        r=requests.get(f"{BASE}/{k}/history",timeout=15)
        r.raise_for_status()
        data=r.json()
        logging.info(f"ARGLY {k} sample: {str(data)[:200]}")
        return data
    except Exception as e:
        logging.error(f"ARGLY {k}:{e}")
        return []

def extraer_valor(item):
    for campo in ["valor","value","v","indice","index","amount","precio","price"]:
        if campo in item:
            try: return float(item[campo])
            except: pass
    for v in item.values():
        try: return float(v)
        except: pass
    return None

def extraer_fecha(item):
    for campo in ["fecha","date","f","periodo","period","mes","month"]:
        if campo in item:
            return str(item[campo])
    return ""

def buscar_en_lista(datos,fecha_str):
    try:
        f=datetime.strptime(fecha_str,"%d/%m/%Y")
        fi=f.strftime("%Y-%m-%d")
        fim=f.strftime("%Y-%m")
        candidatos=[]
        for d in datos:
            fd=extraer_fecha(d)
            if fd<=fi or fd<=fim:
                candidatos.append(d)
        if candidatos: return candidatos[-1]
    except Exception as e: logging.error(f"buscar:{e}")
    return None

async def start(u,c):
    await u.message.reply_text("Bot del Corredor Inmobiliario\n\n/honorarios - Calculadora COCIR\n/actualizar - ICL IPC Casa Propia UVA\n/punitorios - Interes por mora\n/ley - Ley Provincial 13154\n/ayuda")

async def ayuda(u,c):
    await u.message.reply_text("/honorarios - Honorarios COCIR\n/actualizar - Actualiza alquiler automatico\n/punitorios - Interes por mora\n/ley - Ley Provincial 13154\n/cancelar - Salir")

async def ley(u,c):
    await u.message.reply_text("Ley Provincial N 13154 - Corredores Inmobiliarios Santa Fe\n\nhttps://cocir.org.ar/novedades/25/ley-provincial-n-13154/")

async def hon_start(u,c):
    await u.message.reply_text("Honorarios COCIR\n\n1 Venta\n2 Alquiler\n3 Tasacion\n4 Administracion\n\nResponde con el numero.")
    return HON_CAT

async def hon_cat(u,c):
    op=u.message.text.strip()
    if op not in("1","2","3","4"):
        await u.message.reply_text("Responde 1, 2, 3 o 4.")
        return HON_CAT
    c.user_data["hcat"]=op
    if op=="1":
        await u.message.reply_text("Venta - Tipo de inmueble\n\n1 Casas/Dptos/Oficinas/Locales/Galpones/Quintas\n2 Terrenos/Lotes/Nichos\n3 Edificios PH\n4 Consorcios/Fideicomisos\n5 Fondo de Comercio\n6 Campos\n\nResponde con el numero.")
        return HON_SUBTIPO
    elif op=="2":
        await u.message.reply_text("Alquiler - Tipo\n\n1 Vivienda\n2 Locacion comercial\n\nResponde con el numero.")
        return HON_SUBTIPO
    elif op=="3":
        await u.message.reply_text("Tasacion - Tipo\n\n1 Informativa vivienda (minimo 1 JUS)\n2 Tecnica vivienda (minimo 2 JUS)\n3 Industrias/campos/f.comercio (minimo 4 JUS)\n\nResponde con el numero.")
        return HON_TAS_TIPO
    else:
        await u.message.reply_text("Monto mensual de alquiler cobrado? (solo el numero)")
        return HON_MONTO

async def hon_tas_tipo(u,c):
    op=u.message.text.strip()
    if op not in TIPOS_TAS:
        await u.message.reply_text("Responde 1, 2 o 3.")
        return HON_TAS_TIPO
    c.user_data["htastipo"]=op
    await u.message.reply_text(f"Tipo: {TIPOS_TAS[op]['n']}\n\nCual es el valor tasado? (solo el numero en pesos)")
    return HON_MONTO

async def hon_subtipo(u,c):
    op=u.message.text.strip()
    cat=c.user_data["hcat"]
    if cat=="1" and op not in VENTA:
        await u.message.reply_text("Responde del 1 al 6.")
        return HON_SUBTIPO
    if cat=="2" and op not in ALQUILER:
        await u.message.reply_text("Responde 1 o 2.")
        return HON_SUBTIPO
    c.user_data["hsub"]=op
    if cat=="1":
        await u.message.reply_text("Moneda de la venta?\n\n1 Pesos\n2 Dolares\n\nResponde 1 o 2.")
        return HON_MONEDA
    await u.message.reply_text("Valor mensual del alquiler? (solo el numero)")
    return HON_MONTO

async def hon_moneda(u,c):
    op=u.message.text.strip()
    if op not in("1","2"):
        await u.message.reply_text("Responde 1 o 2.")
        return HON_MONEDA
    c.user_data["hmoneda"]=op
    if op=="1":
        await u.message.reply_text("Precio de venta en pesos? (solo el numero)")
    else:
        await u.message.reply_text("Precio de venta en dolares? (solo el numero)")
    return HON_MONTO

async def hon_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["hmonto"]=m
    except:
        await u.message.reply_text("Solo el numero. Ej: 5000000")
        return HON_MONTO
    cat=c.user_data["hcat"]
    if cat in("1","3","4"): return await calcular(u,c,m,None)
    await u.message.reply_text("Cuantos meses dura el contrato? Ej: 24")
    return HON_MESES

async def hon_meses(u,c):
    try:
        m=int(u.message.text.strip())
        assert m>0
        c.user_data["hmeses"]=m
    except:
        await u.message.reply_text("Numero positivo. Ej: 24")
        return HON_MESES
    sub=c.user_data["hsub"]
    if ALQUILER[sub]["fiscal"]:
        await u.message.reply_text("Condicion fiscal del locador:\n\n1 Responsable Inscripto\n2 Monotributista / Exento\n\nResponde 1 o 2.")
        return HON_FISCAL
    return await calcular(u,c,c.user_data["hmonto"],m)

async def hon_fiscal(u,c):
    op=u.message.text.strip()
    if op not in("1","2"):
        await u.message.reply_text("Responde 1 o 2.")
        return HON_FISCAL
    c.user_data["hfiscal"]=op
    return await calcular(u,c,c.user_data["hmonto"],c.user_data["hmeses"])

async def calcular(u,c,monto,meses):
    cat=c.user_data["hcat"]
    if cat=="3":
        jus=obtener_jus()
        hon_mil=monto*0.001
        tt=c.user_data.get("htastipo","1")
        tipo=TIPOS_TAS[tt]
        min_jus=jus*tipo["jus"]
        aplicado=max(hon_mil,min_jus)
        criterio="Minimo JUS" if min_jus>hon_mil else "1 por mil"
        await u.message.reply_text(
            f"Tasacion - {tipo['n']}\n\n"
            f"Valor tasado: {fmt(monto)}\n\n"
            f"1 por mil: {fmt(hon_mil)}\n"
            f"Minimo {tipo['jus']} JUS: {fmt(min_jus)}\n\n"
            f"Se aplica: {criterio}\n"
            f"Honorario: {fmt(aplicado)}\n\n"
            f"1 JUS = {fmt(jus)}\n"
            f"Caja Forense - COCIR"
        )
        return ConversationHandler.END
    if cat=="4":
        hon=monto*0.10
        iva=hon*TASA_IVA
        await u.message.reply_text(
            f"Administracion\n\n"
            f"Alquiler cobrado: {fmt(monto)}\n"
            f"Alicuota: 10%\n"
            f"Honorario neto: {fmt(hon)}\n"
            f"IVA 21%: {fmt(iva)}\n"
            f"Total con IVA: {fmt(hon+iva)}\n\n"
            f"COCIR - Ley 13.154"
        )
        return ConversationHandler.END
    if cat=="1":
        sub=c.user_data["hsub"]
        info=VENTA[sub]
        moneda=c.user_data.get("hmoneda","1")
        hc=monto*info["c"]
        hp=monto*info["p"]
        if moneda=="2":
            blue=obtener_blue()
            if blue:
                hc_ars=hc*blue
                hp_ars=hp*blue
                blue_txt=f"\nCotizacion blue promedio: {fmt(blue)}"
                detalle_c=f"USD {hc:,.2f} = {fmt(hc_ars)}"
                detalle_p=f"USD {hp:,.2f} = {fmt(hp_ars)}"
            else:
                blue_txt="\nNo pude obtener cotizacion blue"
                detalle_c=f"USD {hc:,.2f}"
                detalle_p=f"USD {hp:,.2f}"
            await u.message.reply_text(
                f"Venta - {info['n']}\n\n"
                f"Precio: USD {monto:,.2f}{blue_txt}\n\n"
                f"Comprador ({info['c']*100:.0f}%): {detalle_c}\n"
                f"Propietario ({info['p']*100:.0f}%): {detalle_p}\n\n"
                f"COCIR - Ley 13.154"
            )
        else:
            await u.message.reply_text(
                f"Venta - {info['n']}\n\n"
                f"Precio: {fmt(monto)}\n\n"
                f"Comprador ({info['c']*100:.0f}%): {fmt(hc)}\n"
                f"Propietario ({info['p']*100:.0f}%): {fmt(hp)}\n\n"
                f"COCIR - Ley 13.154"
            )
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
        sel_bloque=f"\nSellado 2.5% {cond}\nBase: {fmt(bs)}\nSellado: {fmt(sel)}\nTotal honor+sellado: {fmt(hl*1.21+sel)}\n"
    await u.message.reply_text(
        f"Alquiler - {info['n']}\n\n"
        f"{fmt(monto)} x {meses} meses\n"
        f"Base: {fmt(base)} Alicuota: {info['al']*100:.0f}%\n\n"
        f"Locatario\nNeto: {fmt(hl)} IVA: {fmt(hl*TASA_IVA)}\nTotal: {fmt(hl*1.21)}\n\n"
        f"Locador\nNeto: {fmt(hd)} IVA: {fmt(hd*TASA_IVA)}\nTotal: {fmt(hd*1.21)}\n"
        f"{sel_bloque}\nCOCIR - Ley 13.154"
    )
    return ConversationHandler.END

async def act_start(u,c):
    await u.message.reply_text("Actualizacion de Alquiler\n\nCada cuanto se actualiza?\n\n1 Mensual\n2 Trimestral\n3 Cuatrimestral\n4 Semestral\n5 Anual\n\nResponde con el numero.")
    return ACT_PERIODO

async def act_periodo(u,c):
    op=u.message.text.strip()
    if op not in PERIODOS:
        await u.message.reply_text("Responde del 1 al 5.")
        return ACT_PERIODO
    c.user_data["aperido"]=op
    await u.message.reply_text(f"Periodo: {PERIODOS[op]}\n\nQue indice usa el contrato?\n\n1 ICL\n2 IPC\n3 Casa Propia\n4 UVA\n\nResponde con el numero.")
    return ACT_INDICE

async def act_indice(u,c):
    op=u.message.text.strip()
    if op not in INDICES:
        await u.message.reply_text("Responde del 1 al 4.")
        return ACT_INDICE
    c.user_data["aindice"]=op
    await u.message.reply_text(f"Indice: {INDICES[op]['n']}\n\nAlquiler actual? (solo el numero)")
    return ACT_MONTO

async def act_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["am"]=m
    except:
        await u.message.reply_text("Solo el numero.")
        return ACT_MONTO
    await u.message.reply_text("Fecha del ultimo ajuste (DD/MM/AAAA)")
    return ACT_FECHA

async def act_fecha(u,c):
    fs=u.message.text.strip()
    try: datetime.strptime(fs,"%d/%m/%Y")
    except:
        await u.message.reply_text("Formato DD/MM/AAAA. Ej: 01/01/2025")
        return ACT_FECHA
    await u.message.reply_text("Consultando datos...")
    m=c.user_data["am"]
    ind=INDICES[c.user_data["aindice"]]
    per=PERIODOS[c.user_data["aperido"]]
    k=ind["k"]
    datos=get_historico(k)
    if not datos:
        await u.message.reply_text(f"No pude obtener datos de {ind['n']}. Intenta mas tarde.")
        return ConversationHandler.END
    if isinstance(datos,dict):
        datos=datos.get("data",datos.get("results",datos.get("items",[])))
    if not isinstance(datos,list) or len(datos)==0:
        await u.message.reply_text(f"Formato inesperado de {ind['n']}. Intenta mas tarde.")
        return ConversationHandler.END
    d0=buscar_en_lista(datos,fs)
    dh=datos[-1]
    if not d0 or not dh:
        await u.message.reply_text("No encontre datos para esa fecha.")
        return ConversationHandler.END
    v0=extraer_valor(d0)
    vh=extraer_valor(dh)
    fh=extraer_fecha(dh)
    if not v0 or not vh or v0==0:
        await u.message.reply_text(f"Error al leer valores. d0={d0} dh={dh}")
        return ConversationHandler.END
    var=(vh/v0)-1
    nm=m*(vh/v0)
    await u.message.reply_text(
        f"Actualizacion - {ind['n']} {per}\n\n"
        f"Fecha inicio: {fs}\n"
        f"Fecha actual: {fh}\n\n"
        f"Variacion: {var*100:.2f}%\n\n"
        f"Alquiler anterior: {fmt(m)}\n"
        f"Incremento: {fmt(nm-m)}\n"
        f"Nuevo alquiler: {fmt(nm)}\n\n"
        f"Fuente: Argly - {ind['n']}"
    )
    return ConversationHandler.END

async def pun_start(u,c):
    await u.message.reply_text("Punitorios\n\nCual es la tasa diaria del contrato?\n\nEj: 1 para 1% diario\nEj: 0.5 para 0.5% diario")
    return PUN_TASA

async def pun_tasa(u,c):
    try:
        t=float(u.message.text.strip().replace(",","."))
        assert 0<t<100
        c.user_data["ptasa"]=t/100
        c.user_data["ptasa_display"]=t
    except:
        await u.message.reply_text("Ingresa un numero. Ej: 1")
        return PUN_TASA
    await u.message.reply_text(f"Tasa: {t:.2f}% diario\n\nMonto adeudado? (solo el numero)")
    return PUN_MONTO

async def pun_monto(u,c):
    try:
        m=float(u.message.text.strip().replace(".","").replace(",","."))
        c.user_data["pm"]=m
    except:
        await u.message.reply_text("Solo el numero.")
        return PUN_MONTO
    await u.message.reply_text("Cuantos dias de mora?")
    return PUN_DIAS

async def pun_dias(u,c):
    try:
        d=int(u.message.text.strip())
        assert d>0
    except:
        await u.message.reply_text("Numero positivo.")
        return PUN_DIAS
    m=c.user_data["pm"]
    tasa=c.user_data["ptasa"]
    tasa_display=c.user_data["ptasa_display"]
    i=m*tasa*d
    await u.message.reply_text(
        f"Punitorios\n\n"
        f"Monto: {fmt(m)}\n"
        f"Tasa: {tasa_display:.2f}% diario\n"
        f"Dias: {d}\n\n"
        f"Interes: {fmt(i)}\n"
        f"Total: {fmt(m+i)}"
    )
    return ConversationHandler.END

async def cancelar(u,c):
    await u.message.reply_text("Cancelado. /ayuda para ver opciones.")
    return ConversationHandler.END

async def desconocido(u,c):
    await u.message.reply_text("Escribe /ayuda para ver los comandos.")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    ch=ConversationHandler(entry_points=[CommandHandler("honorarios",hon_start)],states={HON_CAT:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_cat)],HON_SUBTIPO:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_subtipo)],HON_TAS_TIPO:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_tas_tipo)],HON_MONEDA:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_moneda)],HON_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_monto)],HON_MESES:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_meses)],HON_FISCAL:[MessageHandler(filters.TEXT&~filters.COMMAND,hon_fiscal)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    ca=ConversationHandler(entry_points=[CommandHandler("actualizar",act_start)],states={ACT_PERIODO:[MessageHandler(filters.TEXT&~filters.COMMAND,act_periodo)],ACT_INDICE:[MessageHandler(filters.TEXT&~filters.COMMAND,act_indice)],ACT_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,act_monto)],ACT_FECHA:[MessageHandler(filters.TEXT&~filters.COMMAND,act_fecha)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    cp=ConversationHandler(entry_points=[CommandHandler("punitorios",pun_start)],states={PUN_TASA:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_tasa)],PUN_MONTO:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_monto)],PUN_DIAS:[MessageHandler(filters.TEXT&~filters.COMMAND,pun_dias)]},fallbacks=[CommandHandler("cancelar",cancelar)])
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("ayuda",ayuda))
    app.add_handler(CommandHandler("ley",ley))
    app.add_handler(ch)
    app.add_handler(ca)
    app.add_handler(cp)
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,desconocido))
    print("Bot corriendo...")
    app.run_polling()

if __name__=="__main__":
    main()
