import os
import json
import datetime
import imaplib
import email
from bs4 import BeautifulSoup
import google.generativeai as genai

# Configurazione API Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Credenziali Gmail
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")

# --- RICERCA DINAMICA MODELLO ---
modello_scelto = None
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            if 'flash' in m.name or 'pro' in m.name:
                modello_scelto = m.name.replace("models/", "")
                break
    if not modello_scelto:
        modello_scelto = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods][0]
except Exception:
    modello_scelto = "gemini-1.5-flash"

print(f"Modello AI: {modello_scelto}")
model = genai.GenerativeModel(modello_scelto)
# --------------------------------

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"

def get_emails():
    print("Connessione a Gmail in corso...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")

        # Cerca tutte le email NON lette
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()
        
        email_texts = []
        for e_id in email_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/html":
                                html_body = part.get_payload(decode=True).decode(errors='ignore')
                                soup = BeautifulSoup(html_body, 'html.parser')
                                body += soup.get_text(separator=' ', strip=True)
                                
                                # Proviamo a estrarre i link manualmente per sicurezza
                                for a in soup.find_all('a', href=True):
                                    if "immobiliare.it/annunci" in a['href'] or "idealista.it/immobile" in a['href']:
                                        body += f" [LINK TROVATO: {a['href']}] "
                    else:
                        body = msg.get_payload(decode=True).decode(errors='ignore')
                        
                    if len(body) > 50:
                        email_texts.append(body)
        
        mail.logout()
        return email_texts
    except Exception as e:
        print(f"Errore Gmail: {e}")
        return []

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_existing_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f).get("houses", [])
            except json.JSONDecodeError:
                return []
    return []

def analyze_email_with_ai(email_text, config):
    prompt = f"""
    Sei un estrattore e valutatore immobiliare. Qui sotto c'è il testo grezzo estratto da un'email di avviso immobiliare.
    Il tuo compito è analizzare il testo, capire di che casa si tratta ed estrarre i dati. 
    Se l'email non contiene annunci di case, restituisci esattamente la stringa "NULL".

    Testo Email:
    {email_text[:6000]}

    Parametri Cliente:
    {json.dumps(config, ensure_ascii=False)}

    Se trovi un annuncio valido, valuta il rapporto qualità prezzo e il match con i parametri, poi rispondi SOLO in questo JSON valido:
    {{
        "title": "Titolo annuncio o tipo di casa (es. Villetta a schiera)",
        "price": "Prezzo formattato (es. 150.000 €)",
        "prezzo_numerico": 150000,
        "location": "Paese o Città trovata",
        "description": "Riassunto della casa estratto dall'email",
        "link": "Il link URL esatto dell'annuncio trovato nel testo",
        "image_url": "",
        "commento_ai": "La tua valutazione critica logistica e strutturale",
        "valutazione_prezzo": 8,
        "valutazione_match": 9,
        "consiglio_ribasso": "Consiglio un'offerta a X...",
        "is_ai_render": true
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        testo_pulito = response.text.replace("```json", "").replace("```", "").strip()
        
        if "NULL" in testo_pulito.upper() or len(testo_pulito) < 20:
            return None
            
        analisi = json.loads(testo_pulito)
        analisi["data_inserimento"] = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if not analisi.get("image_url"):
            # Generiamo il render come concordato
            analisi["image_url"] = "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600&q=80"
            analisi["is_ai_render"] = True
            
        return analisi
    except Exception as e:
        print(f"Errore parsing AI: {e}")
        return None

def main():
    config = load_config()
    existing_houses = load_existing_data()
    existing_links = {h.get("link") for h in existing_houses if h.get("link")}
    
    email_texts = get_emails()
    print(f"Trovate {len(email_texts)} nuove email da leggere.")
    
    analyzed_houses = []
    for text in email_texts:
        result = analyze_email_with_ai(text, config)
        if result and result.get("link") not in existing_links:
            analyzed_houses.append(result)
            print(f"Annuncio valido trovato e valutato: {result.get('title')}")
            
    all_houses = analyzed_houses + existing_houses 
    
    output = {
        "last_update": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "houses": all_houses
    }
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
