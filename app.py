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
# ENDPOINT 1: ODBIORNIK WEBHOOKA (NOWA, POPRAWIONA WERSJA)
# ----------------------------------------------------
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    print("--- OTRZYMANO ŻĄDANIE WEBHOOK ---")

    dane_z_tv = None
    try:
        surowy_tekst = request.data.decode('utf-8')
        if not surowy_tekst:
            print("[BŁĄD] Żądanie Webhooka było puste.")
            abort(400)

        print(f"Otrzymano surowy tekst: {surowy_tekst}")
        dane_z_tv = json.loads(surowy_tekst)
    except Exception as e:
        print(f"[KRYTYCZNY BŁĄD] Nie można sparsować JSON. Błąd: {e}")
        print(f"Dane, które spowodowały błąd: {request.data}")
        abort(400)

    # Kontrola bezpieczeństwa
    SEKRETNY_KLUCZ = "TwojSuperTajnyKlucz123"
    if not dane_z_tv or 'sekret' not in dane_z_tv or dane_z_tv['sekret'] != SEKRETNY_KLUCZ:
        print(f"[ODRZUCONO] Błędny klucz bezpieczeństwa lub brak danych.")
        abort(403)

    print(f"[SUKCES] Dane poprawnie sparsowane: {dane_z_tv}")

    interwal = dane_z_tv.get('interwal')
    kolumna = dane_z_tv.get('kolumna')
    wartosc = dane_z_tv.get('wartosc')

    if not all([interwal, kolumna, wartosc]):
        print("[BŁĄD] Brakujące klucze w JSON (interwal, kolumna, wartosc)")
        return jsonify({"status": "błąd", "wiadomość": "Brakujące dane"}), 400

    aktualny_stan = odczytaj_stan()
    if interwal not in aktualny_stan:
        aktualny_stan[interwal] = {}

    aktualny_stan[interwal][kolumna] = wartosc
    zapisz_stan(aktualny_stan)

    print(f"[ZAPISANO] Zaktualizowano {interwal} -> {kolumna} = {wartosc}")
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
