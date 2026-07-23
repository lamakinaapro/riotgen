import requests
import json
import time
import random
import string
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify

app = Flask(__name__)

class RiotAccountGenerator:
    def __init__(self):
        self.base_url = "https://auth.riotgames.com"
        self.mailtm_domain = "mail.tm"
        self.session = requests.Session()
        # Headers essentiels pour l'API Riot
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://auth.riotgames.com",
            "Referer": "https://auth.riotgames.com/flow"
        })

    def generate_random_string(self, length=8):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def create_temp_email(self):
        domain = self.mailtm_domain
        username = "riot" + self.generate_random_string(10) + "@mail.tm"
        
        try:
            response = self.session.post(f"https://api.{domain}/accounts", json={
                "email": username,
                "password": self.generate_random_string(12)
            })
            response.raise_for_status()
            email_data = response.json()
            return {
                "email": email_data["email"],
                "password": email_data["password"],
                "id": email_data["id"]
            }
        except requests.RequestException as e:
            return None

    def check_email_inbox(self, email_id):
        try:
            response = self.session.get(f"https://api.{self.mailtm_domain}/accounts/{email_id}/messages")
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return []

    def validate_email(self, email_id, max_wait_time=60):
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            messages = self.check_email_inbox(email_id)
            for msg in messages:
                subject = msg.get("subject", "").lower()
                if "riot" in subject or "welcome" in subject:
                    msg_id = msg["id"]
                    response = self.session.get(f"https://api.{self.mailtm_domain}/accounts/{email_id}/messages/{msg_id}/body")
                    if response.status_code == 200:
                        html_body = response.json().get("html", "")
                        soup = BeautifulSoup(html_body, "html.parser")
                        
                        # Chercher un lien de validation
                        links = soup.find_all("a")
                        for link in links:
                            href = link.get("href")
                            if href and "auth.riotgames.com" in href:
                                return {"type": "link", "value": href}
                        
                        # Chercher un code à 6 chiffres
                        import re
                        codes = re.findall(r'\b\d{6}\b', html_body)
                        if codes:
                            return {"type": "code", "value": codes[0]}
            
            time.sleep(3)  # Vérifier toutes les 3 secondes
        return None

    def create_account(self, email, password, first_name="Player", last_name="One", locale="en_US", birth_date="1995-01-01"):
        try:
            response = self.session.post(f"{self.base_url}/api/v1/registration", json={
                "account": {
                    "email": email,
                    "username": email.split("@")[0],
                    "firstName": first_name,
                    "lastName": last_name,
                    "locale": locale,
                    "birthDate": birth_date
                },
                "password": password,
                "rememberMe": True
            }, headers={
                "X-Riot-Clientplatform": "ew0KfQ==",
                "X-Riot-Clientversion": "release-0.0.1"
            })
            
            if response.status_code == 201:
                return {"success": True, "message": "Compte créé avec succès !"}
            elif response.status_code == 400:
                error_msg = response.json().get("message", "Erreur 400")
                return {"success": False, "message": f"Erreur 400: {error_msg}"}
            else:
                return {"success": False, "message": f"Erreur {response.status_code}: {response.text}"}
                
        except requests.RequestException as e:
            return {"success": False, "message": f"Exception: {str(e)}"}

    def validate_account(self, email, password, validation_info):
        if not validation_info:
            return {"success": False, "message": "Aucune information de validation trouvée"}
        
        if validation_info["type"] == "link":
            try:
                response = self.session.get(validation_info["value"], allow_redirects=True)
                if response.status_code == 200:
                    return {"success": True, "message": "Email validé via le lien !"}
                else:
                    return {"success": False, "message": f"Validation lien échouée: {response.status_code}"}
            except requests.RequestException as e:
                return {"success": False, "message": f"Exception validation lien: {str(e)}"}
        
        elif validation_info["type"] == "code":
            try:
                flow = self.get_flow_data()
                if not flow:
                    return {"success": False, "message": "Erreur récupération flow pour validation"}
                
                response = self.session.post(f"{self.base_url}/api/v1/registration/verify", json={
                    "email": email,
                    "code": validation_info["value"],
                    "flow": flow.get("flow", "")
                }, headers={
                    "X-Riot-Clientplatform": "ew0KfQ==",
                    "X-Riot-Clientversion": "release-0.0.1"
                })
                
                if response.status_code == 200:
                    return {"success": True, "message": f"Email validé via le code: {validation_info['value']}"}
                else:
                    return {"success": False, "message": f"Validation code échouée: {response.status_code} - {response.text}"}
            except requests.RequestException as e:
                return {"success": False, "message": f"Exception validation code: {str(e)}"}
        
        return {"success": False, "message": "Type de validation inconnu"}

    def get_flow_data(self):
        try:
            response = self.session.post(f"{self.base_url}/api/v1/clients", json={
                "client": "riot-client"
            })
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    def generate_account(self):
        email_data = self.create_temp_email()
        if not email_data:
            return {"success": False, "message": "Erreur : Échec de la création de l'email jetable."}
        
        email = email_data["email"]
        email_password = email_data["password"]
        email_id = email_data["id"]
        
        riot_password = self.generate_random_string(10) + "!"
        result = self.create_account(email, riot_password)
        
        if not result["success"]:
            return {"success": False, "message": result['message']}
        
        validation_info = self.validate_email(email_id)
        if not validation_info:
            return {"success": False, "message": "Aucun email de validation reçu."}
        
        validation_result = self.validate_account(email, riot_password, validation_info)
        
        account_info = {
            "riot_username": email.split("@")[0],
            "riot_email": email,
            "riot_password": riot_password,
            "email_password": email_password,
            "email_id": email_id,
            "validation_status": validation_result["message"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if validation_result["success"]:
            account_info["success"] = True
        else:
            account_info["success"] = False
            account_info["message"] = validation_result["message"]
            
        return account_info

# Route principale : affiche la page HTML
@app.route('/')
def index():
    return render_template('index.html')

# Route API : lance la génération du compte
@app.route('/api/generate', methods=['POST'])
def generate_riot_account():
    try:
        generator = RiotAccountGenerator()
        account = generator.generate_account()
        return jsonify(account)
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Erreur serveur : {str(e)}"
        }), 500

if __name__ == '__main__':
    # Lancer le serveur sur le port 5000
    app.run(debug=True, port=5000)
