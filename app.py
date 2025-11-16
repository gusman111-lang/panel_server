import json
import os
import threading
from flask import Flask, request, jsonify, abort

# Inicjalizacja aplikacji Flask
app = Flask(__name__)

# Nazwa pliku do przechowywania stanu i blokada (ważne!)
STAN_PLIK = 'stan.json'
# Blokada (threading.Lock) zapobiega błędom, 
# gdyby dwa żądania przyszły w tej samej chwili.
lock = threading.Lock()

# In-memory storage jako backup jeśli plik się nie otwiera
in_memory_stan = {}

# ----------------------------------------------------
# FUNKCJE POMOCNICZE (ODCZYT I ZAPIS DO PLIKU)
# ----------------------------------------------------

def odczytaj_stan():
    """Bezpiecznie odczytuje dane z pliku JSON."""
    global in_memory_stan
    with lock:
        try:
            # Spróbuj czytać z pliku
            if os.path.exists(STAN_PLIK):
                with open(STAN_PLIK, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    in_memory_stan = data
                    return data
        except Exception as e:
            print(f"[OSTRZEŻENIE] Błąd odczytu pliku: {e}")
        
        # Jeśli plik nie istnieje lub nie można go czytać, zwróć co jest w pamięci
        return in_memory_stan

def zapisz_stan(dane):
    """Bezpiecznie zapisuje dane do pliku JSON i do pamięci."""
    global in_memory_stan
    with lock:
        # Zawsze zapisz do pamięci
        in_memory_stan = dane.copy()
        
        # Spróbuj zapisać do pliku
        try:
            with open(STAN_PLIK, 'w', encoding='utf-8') as f:
                json.dump(dane, f, indent=4, ensure_ascii=False)
                print(f"[OK] Zapisano do pliku: {STAN_PLIK}")
        except Exception as e:
            print(f"[OSTRZEŻENIE] Nie udało się zapisać do pliku: {e}")
            print(f"[INFO] Dane przechowywane w pamięci (in-memory)")

# ----------------------------------------------------
# ENDPOINT 1: ODBIORNIK WEBHOOKA (dla TradingView)
# ----------------------------------------------------
# Ten endpoint będzie nasłuchiwał na żądania POST z TradingView
# Adres: http://TWOJADOMENA.com/webhook
# ----------------------------------------------------

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Pobierz dane JSON wysłane przez TradingView
    dane_z_tv = request.json
    
    print(f"\n>>> WEBHOOK OTRZYMANY <<<")
    print(f"Dane: {dane_z_tv}")

    # --- BEZPIECZEŃSTWO (BARDZO WAŻNE!) ---
    # Ustawiamy "sekretny klucz", aby nikt inny nie mógł wysyłać 
    # danych do naszego serwera.
    SEKRETNY_KLUCZ = "TwojSuperTajnyKlucz123" # ZMIEŃ TO!

    # Sprawdzamy, czy dane z TV zawierają poprawny klucz
    if not dane_z_tv or 'sekret' not in dane_z_tv or dane_z_tv['sekret'] != SEKRETNY_KLUCZ:
        print(f"[ODRZUCONO] Błędny klucz lub brak danych.")
        return jsonify({"status": "błąd", "wiadomość": "Nieautoryzowany"}), 403

    # Dane są bezpieczne, przetwarzamy je
    print(f"[✓] Klucz poprawny")

    # Kluczowe dane (możemy je dowolnie zdefiniować w Pine Script)
    interwal = dane_z_tv.get('interwal') # np. "1h"
    kolumna = dane_z_tv.get('kolumna')   # np. "EMA_Krotka"
    wartosc = dane_z_tv.get('wartosc')   # np. "KUPUJ"

    if not all([interwal, kolumna, wartosc]):
        print("[BŁĄD] Brakujące dane (interwal, kolumna, wartosc)")
        return jsonify({"status": "błąd", "wiadomość": "Brakujące dane"}), 400

    # 1. Odczytaj aktualny stan panelu z pliku
    aktualny_stan = odczytaj_stan()

    # 2. Zaktualizuj stan (np. stan['1h']['EMA_Krotka'] = 'KUPUJ')
    if interwal not in aktualny_stan:
        aktualny_stan[interwal] = {}
    
    aktualny_stan[interwal][kolumna] = wartosc

    # 3. Zapisz nowy stan z powrotem do pliku
    zapisz_stan(aktualny_stan)

    # 4. Odpowiedz TradingView, że wszystko jest OK
    print(f"[✓] ZAPISANO: {interwal} -> {kolumna} = {wartosc}")
    print(f"Aktualny stan: {json.dumps(aktualny_stan, ensure_ascii=False)}\n")
    
    return jsonify({"status": "sukces", "wiadomość": f"Zaktualizowano {interwal}"})

# ----------------------------------------------------
# ENDPOINT 2: API DLA WIDGETU (dla Androida)
# ----------------------------------------------------
# Ten endpoint będzie udostępniał dane dla Twojego widgetu
# Adres: http://TWOJADOMENA.com/stan
# ----------------------------------------------------

@app.route('/stan', methods=['GET'])
def get_stan():
    """Wysyła cały aktualny stan panelu w formacie JSON."""
    stan = odczytaj_stan()
    return jsonify(stan)

# Endpoint główny
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "ok", "message": "Serwer Panel działa"})

# ----------------------------------------------------
# URUCHOMIENIE SERWERA (do testów lokalnych)
# ----------------------------------------------------
if __name__ == '__main__':
    # Uruchom serwer na lokalnym komputerze do testów
    # Dostępny pod adresem: http://127.0.0.1:5000
    app.run(debug=True, port=5000)


# ----------------------------------------------------
# ENDPOINT 1: ODBIORNIK WEBHOOKA (NOWA, POPRAWIONA WERSJA)
# ----------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    """Endpoint root - sprawdzenie czy serwer żyje."""
    return jsonify({"status": "ok", "message": "Serwer Wataha Scanner działa"})

@app.route('/webhook', methods=['POST', 'GET'])
def handle_webhook():
    """Odbiera alerty z TradingView i zapisuje do stan.json"""
    print("\n" + "="*60)
    print("--- OTRZYMANO ŻĄDANIE WEBHOOK ---")
    print(f"Metoda: {request.method}")
    print(f"Content-Type: {request.content_type}")
    print("="*60)

    dane_z_tv = None
    try:
        # Czytaj surowe dane (raw request body)
        surowy_tekst = request.data.decode('utf-8') if request.data else ""
        
        if not surowy_tekst:
            print("[BŁĄD] Żądanie Webhooka było puste.")
            return jsonify({"status": "błąd", "wiadomość": "Żądanie puste"}), 400

        print(f"✓ Otrzymano surowy tekst ({len(surowy_tekst)} bajtów): {surowy_tekst[:200]}")
        
        # Sparsuj JSON
        dane_z_tv = json.loads(surowy_tekst)
        print(f"✓ JSON sparsowany pomyślnie")
        
    except json.JSONDecodeError as e:
        print(f"[BŁĄD JSON] Nie można sparsować JSON: {e}")
        print(f"Dane: {request.data}")
        return jsonify({"status": "błąd", "wiadomość": f"Invalid JSON: {str(e)}"}), 400
    except Exception as e:
        print(f"[KRYTYCZNY BŁĄD] {e}")
        return jsonify({"status": "błąd", "wiadomość": str(e)}), 400

    # === WERYFIKACJA KLUCZA ===
    SEKRETNY_KLUCZ = "TwojSuperTajnyKlucz123"
    
    if not dane_z_tv:
        print("[ODRZUCONO] Brak danych")
        return jsonify({"status": "błąd", "wiadomość": "Brak danych"}), 403
    
    klucz_z_tv = dane_z_tv.get('sekret')
    if klucz_z_tv != SEKRETNY_KLUCZ:
        print(f"[ODRZUCONO] Błędny klucz. Oczekiwano: '{SEKRETNY_KLUCZ}', otrzymano: '{klucz_z_tv}'")
        return jsonify({"status": "błąd", "wiadomość": "Nieautoryzowany"}), 403

    print(f"✓ Klucz bezpieczeństwa poprawny")
    print(f"✓ Dane poprawnie sparsowane: {dane_z_tv}")

    # === WYCIĄGNIJ DANE ===
    interwal = dane_z_tv.get('interwal')
    kolumna = dane_z_tv.get('kolumna')
    wartosc = dane_z_tv.get('wartosc')

    if not all([interwal, kolumna, wartosc]):
        print(f"[BŁĄD] Brakujące pola. interwal={interwal}, kolumna={kolumna}, wartosc={wartosc}")
        return jsonify({"status": "błąd", "wiadomość": "Brakujące pola: interwal, kolumna, wartosc"}), 400

    # === ZAPISZ DO PLIKU ===
    try:
        aktualny_stan = odczytaj_stan()
        if interwal not in aktualny_stan:
            aktualny_stan[interwal] = {}

        aktualny_stan[interwal][kolumna] = wartosc
        zapisz_stan(aktualny_stan)
        
        print(f"✓ [ZAPISANO] {interwal} -> {kolumna} = {wartosc}")
        print(f"✓ Aktualny stan: {json.dumps(aktualny_stan, ensure_ascii=False)}")
        print("="*60 + "\n")
        
        return jsonify({"status": "sukces", "wiadomość": f"Zaktualizowano {interwal}"})
    except Exception as e:
        print(f"[BŁĄD ZAPISU] {e}")
        return jsonify({"status": "błąd", "wiadomość": f"Błąd zapisu: {str(e)}"}), 500

# ----------------------------------------------------
# ENDPOINT 2: API DLA WIDGETU (dla Androida)
# ----------------------------------------------------
# Ten endpoint będzie udostępniał dane dla Twojego widgetu
# Adres: http://TWOJADOMENA.com/stan
# ----------------------------------------------------

@app.route('/stan', methods=['GET'])
def get_stan():
    """Wysyła cały aktualny stan panelu w formacie JSON."""
    stan = odczytaj_stan()
    return jsonify(stan)

# ----------------------------------------------------
# URUCHOMIENIE SERWERA (do testów lokalnych)
# ----------------------------------------------------
if __name__ == '__main__':
    # Uruchom serwer na lokalnym komputerze do testów
    # Dostępny pod adresem: http://127.0.0.1:5000
    app.run(debug=True, port=5000)
