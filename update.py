import os
import json
import datetime
import imaplib
import email
from bs4 import BeautifulSoup
import google.generativeai as genai

# Configurazione API Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Credenziali Gmail (prelevate dai Secrets di GitHub)
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

print(f"Modello AI selezionato: {modello_scelto}")
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

        # Cerca solo le email NON LETTE
        status, messages = mail.search(None, "UNSEEN")
        if not messages[0]:
            print("Nessuna nuova email non letta trovata.")
            return []
            
        email_ids = messages[0].split()
        email_texts = []
        
        for e_id in email_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    body = ""
                    link_estratti = []
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/html":
                                html_body = part.get_payload(decode=True).decode(errors='ignore')
                                soup = BeautifulSoup(html_body, 'html.parser')
                                body += soup.get_text(separator=' ', strip=True)
                                
                                # FILTRO AGGIORNATO: Più flessibile per catturare i link di reindirizzamento
                                domini_validi = ["immobiliare.it", "idealista.it", "casa.it", "subito.it"]
                                for a in soup.find_all('a', href=True):
                                    href = a['href']
                                    # Accetta i link dei domini scelti, ma scarta mappe e pagine generiche agenzie
                                    if any(dominio in href for dominio in domini_validi) and "agenzie" not in href and "maps" not in href:
                                        link_estratti.append(href)
                    else:
                        body = msg.get_payload(decode=True).decode(errors='ignore')
                        
                    if len(body) > 50:
                        # Uniamo il testo dell'email alla lista dei link "puliti" trovati
                        testo_per_ai = body + "\n\n--- LINK DIRETTI TROVATI NELL'EMAIL ---\n" + "\n".join(list(set(link_estratti)))
                        email_texts.append(testo_per_ai)
        
        mail.logout()
        return email_texts
    except Exception as e:
        print(f"Errore durante l'accesso a Gmail: {e}")
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
    Sei un consulente immobiliare esperto. Analizza il testo di questa email e identifica l'annuncio della casa.
    Se il testo non contiene un annuncio di una casa in vendita, rispondi solo "NULL".

    Testo da analizzare:
    {email_text[:7000]}

    Parametri di ricerca del cliente:
    {json.dumps(config, ensure_ascii=False)}

    Restituisci i dati estratti ESCLUSIVAMENTE in questo formato JSON:
    {{
        "title": "Titolo descrittivo dell'immobile",
        "price": "Prezzo esatto (es. 145.000 €)",
        "prezzo_numerico": 145000,
        "location": "Comune o zona (es. Trescore Cremasco)",
        "description": "Breve riassunto dei dettagli principali",
        "link": "DEVI estrarre l'indirizzo web dell'annuncio dalla sezione LINK DIRETTI TROVATI. Ignora i link a mappe o siti esterni.",
        "image_url": "",
        "commento_ai": "Tuo parere professionale basato sui parametri del cliente",
        "valutazione_prezzo": 1-10,
        "valutazione_match": 1-10,
        "consiglio_ribasso": "Suggerimento sulla trattativa",
        "is_ai_render": true
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        testo_pulito = response.text.replace("```json", "").replace("```", "").strip()
        
        if "NULL" in testo_pulito.upper() or len(testo_pulito) < 30:
            return None
            
        analisi = json.loads(testo_pulito)
        analisi["data_inserimento"] = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Gestione immagine di fallback (Render AI)
        if not analisi.get("image_url"):
            analisi["image_url"] = "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600&q=80"
            analisi["is_ai_render"] = True
            
        return analisi
    except Exception as e:
        print(f"Errore durante l'analisi AI: {e}")
        return None

def main():
    config = load_config()
    existing_houses = load_existing_data()
    # Identifichiamo le case già presenti per non creare duplicati
    existing_links = {h.get("link") for h in existing_houses if h.get("link")}
    
    email_texts = get_emails()
    print(f"Nuove email analizzabili: {len(email_texts)}")
    
    analyzed_houses = []
    for text in email_texts:
        result = analyze_email_with_ai(text, config)
        # Salviamo solo se l'AI ha trovato un annuncio e se non lo abbiamo già in archivio
        if result and result.get("link") and result.get("link") not in existing_links:
            analyzed_houses.append(result)
            print(f"Nuovo annuncio identificato: {result.get('title')} a {result.get('location')}")
            
    # Le nuove case appaiono per prime
    all_houses = analyzed_houses + existing_houses 
    
    output = {
        "last_update": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "houses": all_houses
    }
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
    print("Aggiornamento data.json completato.")

if __name__ == "__main__":
    main()
    
