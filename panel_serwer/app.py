import json
import os
import threading
from flask import Flask, request, jsonify, abort

# Inicjalizacja aplikacji Flask
app = Flask(__name__)

# Nazwa pliku do przechowywania stanu i blokada (ważne!)
# Użyj pełnej ścieżki do pliku, aby uniknąć problemów z uprawnieniami
STAN_PLIK = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stan.json')
# Blokada (threading.Lock) zapobiega błędom, 
# gdyby dwa żądania przyszły w tej samej chwili.
lock = threading.Lock()

# ----------------------------------------------------
# FUNKCJE POMOCNICZE (ODCZYT I ZAPIS DO PLIKU)
# ----------------------------------------------------

def odczytaj_stan():
    """Bezpiecznie odczytuje dane z pliku JSON."""
    with lock:
        # Jeśli plik nie istnieje, stwórz go z pustym stanem
        if not os.path.exists(STAN_PLIK):
            with open(STAN_PLIK, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            return {}
            
        # Odczytaj istniejący plik
        try:
            with open(STAN_PLIK, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Jeśli plik jest uszkodzony, zresetuj go
            return {}

def zapisz_stan(dane):
    """Bezpiecznie zapisuje dane do pliku JSON."""
    with lock:
        with open(STAN_PLIK, 'w', encoding='utf-8') as f:
            json.dump(dane, f, indent=4, ensure_ascii=False)

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

    # --- BEZPIECZEŃSTWO (BARDZO WAŻNE!) ---
    # Ustawiamy "sekretny klucz", aby nikt inny nie mógł wysyłać 
    # danych do naszego serwera.
    SEKRETNY_KLUCZ = "TwojSuperTajnyKlucz123" # ZMIEŃ TO!

    # Sprawdzamy, czy dane z TV zawierają poprawny klucz
    if not dane_z_tv or 'sekret' not in dane_z_tv or dane_z_tv['sekret'] != SEKRETNY_KLUCZ:
        print(f"Odrzucono żądanie: Błędny klucz lub brak danych.")
        abort(403)  # Forbidden (Odmowa dostępu)

    # Dane są bezpieczne, przetwarzamy je
    print(f"Otrzymano dane: {dane_z_tv}")

    # Kluczowe dane (możemy je dowolnie zdefiniować w Pine Script)
    interwal = dane_z_tv.get('interwal') # np. "1h"
    kolumna = dane_z_tv.get('kolumna')   # np. "EMA_Krotka"
    wartosc = dane_z_tv.get('wartosc')   # np. "KUPUJ"

    if not all([interwal, kolumna, wartosc]):
        print("Odrzucono: Brakujące dane (interwal, kolumna, wartosc)")
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

# ----------------------------------------------------
# URUCHOMIENIE SERWERA (do testów lokalnych)
# ----------------------------------------------------
if __name__ == '__main__':
    # Uruchom serwer na lokalnym komputerze do testów
    # Dostępny pod adresem: http://127.0.0.1:5000
    app.run(debug=True, port=5000)
