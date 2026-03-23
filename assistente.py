import os, tempfile, time, re, threading, webbrowser, queue, json
import speech_recognition as sr
from groq import Groq
from gtts import gTTS
import pygame
import pyautogui

#   CONFIGURAÇÃO

# ⚠️ Lembrete de segurança: considere usar variáveis de ambiente no futuro!
GROQ_API_KEY = "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"
MODELO       = "llama-3.1-8b-instant"
NOME         = "maestro"
IDIOMA       = "pt-BR"
VOLUME       = 0.9

APPS = {
    "bloco de notas": "notepad.exe",
    "calculadora":    "calc.exe",
    "explorador":     "explorer.exe",
    "chrome":         "start chrome",
    "navegador":      "start chrome",
    "edge":           "start msedge",
    "firefox":        "start firefox",
    "spotify":        "start spotify",
    "discord":        "start discord",
    "paint":          "mspaint.exe",
    "task manager":   "taskmgr.exe",
    "word":           "start winword",
    "excel":          "start excel",
}

SITES = {
    "youtube":   "https://youtube.com",
    "google":    "https://google.com",
    "gmail":     "https://mail.google.com",
    "github":    "https://github.com",
    "netflix":   "https://netflix.com",
    "whatsapp":  "https://web.whatsapp.com",
    "instagram": "https://instagram.com",
    "twitter":   "https://twitter.com",
    "facebook":  "https://facebook.com",
    "twitch":    "https://twitch.tv",
    "reddit":    "https://reddit.com",
    "amazon":    "https://amazon.com.br",
}

PALAVRAS_PARAR = ["para", "cala", "silêncio", "chega", "stop", "cancela"]
PALAVRAS_SAIR  = ["encerrar", "sair", "tchau", "desligar"]

#   ESTADO

class Estado:
    DORMINDO    = "dormindo"
    AGUARDANDO  = "aguardando"
    PROCESSANDO = "processando"
    modo        = DORMINDO
    falando     = False
    parar_fala  = False
    rodando     = True

estado = Estado()
fila_texto = queue.Queue()

#   VOZ

pygame.mixer.init()
pygame.mixer.music.set_volume(VOLUME)

def falar(texto: str):
    estado.falando    = True
    estado.parar_fala = False
    print(f"\n{NOME.capitalize()}: {texto}")
    frases = re.split(r'(?<=[.!?,;])\s+', texto)
    for frase in frases:
        if estado.parar_fala:
            pygame.mixer.music.stop()
            break
        if frase.strip():
            _tocar(frase.strip())
    estado.falando    = False
    estado.parar_fala = False

def _tocar(texto: str):
    try:
        tts = gTTS(text=texto, lang="pt", slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            caminho = f.name
        tts.save(caminho)
        pygame.mixer.music.set_volume(VOLUME)
        pygame.mixer.music.load(caminho)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if estado.parar_fala:
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)
        pygame.mixer.music.unload()
        os.remove(caminho)
    except Exception as e:
        print(f"[Erro voz: {e}]")

#   MICROFONE

def thread_microfone():
    rec = sr.Recognizer()
    rec.pause_threshold          = 0.8
    rec.dynamic_energy_threshold = True
    rec.energy_threshold         = 300

    with sr.Microphone() as fonte:
        print("[Calibrando microfone...]")
        rec.adjust_for_ambient_noise(fonte, duration=1.5)
        print("[Pronto! Pode falar]\n")

        while estado.rodando:
            try:
                audio = rec.listen(fonte, timeout=3, phrase_time_limit=15)
                texto = rec.recognize_google(audio, language=IDIOMA).lower().strip()
                if texto:
                    print(f"[Ouviu]: {texto}")
                    fila_texto.put(texto)
            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as e:
                print(f"[Mic erro: {e}]")
                time.sleep(0.5)


#   INTERPRETADOR DE COMANDOS (CURTO-CIRCUITO LOCAL)
ORDINAIS = {
    "primeiro": 1, "primeira": 1, "segundo":  2, "segunda":  2,
    "terceiro": 3, "terceira": 3, "quarto":   4, "quarta":   4,
    "quinto":   5, "quinta":   5, "sexto":    6, "sexta":    6,
}

def _extrair_ordinal(texto: str) -> int | None:
    for palavra, num in ORDINAIS.items():
        if palavra in texto:
            return num
    m = re.search(r'\b(\d+)[oaº°]?\b', texto)
    if m:
        return int(m.group(1))
    return None

def _extrair_site(texto: str):
    for nome, url in SITES.items():
        if nome in texto:
            return nome, url
    return None, None

def _extrair_app(texto: str):
    for nome, cmd in APPS.items():
        if nome in texto:
            return nome, cmd
    return None, None

def interpretar(texto: str):
    """
    Interpreta comandos rápidos para execução local.
    A pesquisa complexa foi removida para deixar o Groq assumir o controle web.
    """
    t = texto.lower().strip()
    acoes = []

    palavras_acao = [
        "abr", "entr", "acessa", "vai", "abre", "pra", "pro",
        "pesquis", "busc", "procur", "clic", "seleciona",
        "print", "screenshot", "captura", "rola", "scroll", "desce", "escola",
        "volume", "muta", "silencia", "fechar", "fecha", "minimiza", "maximiza", "digit",
    ]

    palavras_conversa = [
        "o que é", "o que são", "como funciona", "como fazer",
        "qual é", "quais são", "quando foi", "quem é", "onde fica",
        "me explica", "me conta", "me fala", "explica",
        "por que", "porque", "diferença entre", "me dá", "quanto", "quantos",
    ]

    if any(p in t for p in palavras_conversa):
        return None

    if not any(p in t for p in palavras_acao):
        return None

    # ─── ABRIR SITE RÁPIDO ─────────────────────────────────────
    palavras_abrir_site = ["abr", "entr", "acessa", "vai", "abre", "ir para", "ir pro", "ir pra", "manda pro", "manda pra"]
    if any(p in t for p in palavras_abrir_site) and not any(p in t for p in ["pesquisa", "busca"]):
        nome_site, url_site = _extrair_site(t)
        if url_site:
            acoes.append(("url", url_site, f"Abrindo {nome_site}."))
            return acoes

    # ─── ABRIR APP RÁPIDO ──────────────────────────────────────
    palavras_abrir_app = ["abr", "abre", "executar", "iniciar", "liga", "roda"]
    if any(p in t for p in palavras_abrir_app):
        nome_app, cmd_app = _extrair_app(t)
        if cmd_app:
            acoes.append(("app", cmd_app, f"Abrindo {nome_app}."))
            return acoes

    # ─── CLICAR RÁPIDO (TAB/ENTER) ─────────────────────────────
    if any(p in t for p in ["clic", "seleciona", "escolhe", "abre o"]):
        posicao = _extrair_ordinal(t)
        if posicao:
            acoes.append(("clicar", posicao, f"{posicao}º resultado clicado."))
            return acoes

    # ─── SCREENSHOT ────────────────────────────────────────────
    if any(p in t for p in ["print", "screenshot", "captura da tela", "foto da tela"]):
        acoes.append(("screenshot", None, None))
        return acoes

    # ─── SCROLL ────────────────────────────────────────────────
    if any(p in t for p in ["rola", "scroll", "desce", "descer", "baixa a tela", "escola"]):
        direcao = "cima" if any(p in t for p in ["cima", "subi", "topo"]) else "baixo"
        acoes.append(("scroll", direcao, f"Rolando para {direcao}."))
        return acoes

    # ─── VOLUME ────────────────────────────────────────────────
    if "volume" in t:
        if any(p in t for p in ["sobe", "aumenta", "mais alto", "subir"]):
            acoes.append(("volume", "up", "Volume aumentado."))
            return acoes
        if any(p in t for p in ["baixa", "diminui", "menos", "baixar"]):
            acoes.append(("volume", "down", "Volume diminuído."))
            return acoes
        if any(p in t for p in ["muta", "silencia", "mudo"]):
            acoes.append(("volume", "mute", "Mutado."))
            return acoes

    return None  # Passa o comando complexo (como pesquisas) para o Groq Autônomo

def executar(acoes: list) -> str:
    msgs = []
    for acao in acoes:
        tipo = acao[0]
        arg  = acao[1]
        msg  = acao[2] if len(acao) > 2 else None

        if tipo == "url":
            webbrowser.open(arg)
            if msg: msgs.append(msg)
            time.sleep(3.5)

        elif tipo == "app":
            os.system(arg)
            if msg: msgs.append(msg)
            time.sleep(1.5)

        elif tipo == "clicar":
            posicao = arg
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.5)
            pyautogui.press("escape")
            time.sleep(0.5)
            tabs = posicao + 4
            for _ in range(tabs):
                pyautogui.press("tab")
                time.sleep(0.18)
            pyautogui.press("enter")
            if msg: msgs.append(msg)

        elif tipo == "esperar":
            time.sleep(arg)

        elif tipo == "screenshot":
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            nome    = f"screenshot_{int(time.time())}.png"
            pyautogui.screenshot(os.path.join(desktop, nome))
            msgs.append(f"Screenshot salvo como {nome}.")

        elif tipo == "scroll":
            pyautogui.scroll(400 if arg == "cima" else -400)
            if msg: msgs.append(msg)

        elif tipo == "volume":
            tecla = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}[arg]
            repeticoes = 1 if arg == "mute" else 5
            for _ in range(repeticoes):
                pyautogui.press(tecla)
            if msg: msgs.append(msg)

    return " ".join(m for m in msgs if m)

#   GROQ
cliente_groq = Groq(api_key=GROQ_API_KEY)

historico = [
    {
        "role": "system",
        "content": (
            "Você é Maestro, um assistente autônomo com controle do teclado e mouse do PC do usuário. "
            "Você NÃO vê a tela, então navegue inteligentemente usando atalhos de teclado. "
            "Sempre responda OBRIGATORIAMENTE no formato JSON contendo uma lista de ações. "
            "As ações permitidas são:\n"
            "1. 'falar': Responder algo em voz alta ao usuário.\n"
            "2. 'tecla': Apertar uma tecla (ex: 'win', 'enter', 'tab', 'esc', 'down', 'up', 'space').\n"
            "3. 'escrever': Digitar um texto.\n"
            "4. 'atalho': Teclas simultâneas separadas por + (ex: 'ctrl+c', 'alt+tab', 'ctrl+l' para barra do navegador, 'ctrl+t' nova aba).\n"
            "5. 'comando_cmd': Executar no terminal (ex: 'start chrome https://youtube.com', 'calc').\n"
            "6. 'scroll': Rolar a tela (ex: -500 para baixo, 500 para cima).\n"
            "7. 'esperar': Pausa em segundos (ex: 1.5). Use antes de digitar algo em janelas que acabaram de abrir.\n"
            "8. 'clicar': Clicar com o mouse (valores: 'esquerda', 'direita', 'duplo').\n\n"
            "DICAS DE NAVEGAÇÃO:\n"
            "- Para pesquisar no YouTube: abra o chrome no youtube, espere, use 'tab' 4 vezes para chegar na barra de busca, escreva e aperte 'enter'.\n"
            "- Para pesquisar no Google: use comando_cmd 'start chrome https://google.com/search?q=TERMO'.\n\n"
            "Exemplo de JSON de resposta:\n"
            "{\n"
            '  "comandos": [\n'
            '    {"acao": "falar", "valor": "Procurando isso agora mesmo."},\n'
            '    {"acao": "comando_cmd", "valor": "start chrome https://google.com/search?q=receita+de+bolo"}\n'
            "  ]\n"
            "}\n"
            "Se for apenas uma conversa, use a ação 'falar'. Retorne APENAS um JSON válido."
        )
    }
]

def perguntar_groq(mensagem: str):
    historico.append({"role": "user", "content": mensagem})
    try:
        r = cliente_groq.chat.completions.create(
            model=MODELO, 
            messages=historico,
            temperature=0.2, 
            max_tokens=800,
            response_format={"type": "json_object"} 
        )
        texto = r.choices[0].message.content
        historico.append({"role": "assistant", "content": texto})

        # Transforma o texto do Groq em comandos reais
        dados = json.loads(texto)
        for cmd in dados.get("comandos", []):
            acao = cmd.get("acao")
            valor = cmd.get("valor")

            print(f"[Executando IA]: {acao} -> {valor}")

            if acao == "falar":
                falar(str(valor))
            elif acao == "tecla":
                pyautogui.press(str(valor))
            elif acao == "escrever":
                pyautogui.write(str(valor), interval=0.03)
            elif acao == "atalho":
                teclas = str(valor).split('+')
                pyautogui.hotkey(*teclas)
            elif acao == "comando_cmd":
                os.system(str(valor))
            elif acao == "scroll":
                pyautogui.scroll(int(valor))
            elif acao == "esperar":
                time.sleep(float(valor))
            elif acao == "clicar":
                if valor == "duplo":
                    pyautogui.doubleClick()
                elif valor == "direita":
                    pyautogui.click(button='right')
                else:
                    pyautogui.click(button='left')

    except Exception as e:
        historico.pop()
        print(f"[Erro IA]: {e}")
        falar("Desculpe, tive um problema para processar esse comando de sistema.")

#   EXECUTAR COMANDO

def _executar_comando(texto: str):
    try:
        if any(p in texto for p in PALAVRAS_SAIR):
            falar("Até logo!")
            estado.rodando = False
            return

        # 1. Tenta interpretar como comando rápido
        acoes = interpretar(texto)
        if acoes:
            resultado = executar(acoes)
            if resultado:
                falar(resultado)
            return

        # 2. Conversa com Groq Autônomo
        print("[→ Groq (Modo Autônomo)]")
        perguntar_groq(texto)

    finally:
        if estado.rodando:
            estado.modo = Estado.AGUARDANDO
            print(f"[Ativo — Ouvindo o próximo comando...]\n")

#   PROCESSADOR
def thread_processador():
    while estado.rodando:
        try:
            texto = fila_texto.get(timeout=1)
        except queue.Empty:
            continue

        if estado.falando and any(p in texto for p in PALAVRAS_PARAR):
            print("[Interrompendo fala]")
            estado.parar_fala = True
            continue

        if estado.modo == Estado.DORMINDO:
            if NOME in texto:
                print("[Wake word!]")
                estado.modo = Estado.AGUARDANDO
                threading.Thread(target=falar, args=("Sim?",), daemon=True).start()
            continue

        if estado.modo == Estado.AGUARDANDO:
            if len(texto.split()) < 2 and texto not in PALAVRAS_SAIR:
                continue
            print(f"Você: {texto}")
            estado.modo = Estado.PROCESSANDO
            threading.Thread(target=_executar_comando, args=(texto,), daemon=True).start()
            continue

#   INÍCIO
def iniciar():
    print("=" * 56)
    print(f"  {NOME.capitalize()} — Agente Autônomo")
    print(f"  Wake word  : '{NOME.capitalize()}'")
    print(f"  Parar fala : 'para' ou 'cala'")
    print(f"  Encerrar   : 'tchau' ou 'encerrar'")
    print(f"  Segurança  : mouse no canto superior esquerdo")
    print("=" * 56)

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.25

    t_mic  = threading.Thread(target=thread_microfone,   daemon=True)
    t_proc = threading.Thread(target=thread_processador, daemon=True)
    t_mic.start()
    t_proc.start()

    time.sleep(2.5)
    falar(f"Olá! Sou o {NOME.capitalize()}. Me chame pelo nome quando precisar.")

    try:
        while estado.rodando:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[Encerrando]")
        estado.rodando = False

    print("Encerrado.")

if __name__ == "__main__":
    iniciar()