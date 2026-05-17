import sys
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig

# === AQUÍ EMPIEZA EL SERVIDOR WEB ===
app = Flask(__name__)
CORS(app)

RPC_URL = "https://mainnet.helius-rpc.com/?api-key=d644072d-c54e-4f39-afa4-126063e96146"

@app.route('/', methods=['GET'])
def home():
    return "🚀 VELOCE RENDER SERVER IS RUNNING"

@app.route('/api/build-tx', methods=['POST'])
def build_tx():
    try:
        # Extraemos los datos que nos envía la extensión
        req_data = request.get_json(force=True)
        priv_key = req_data.get('privateKey', '').strip()
        opcion_action = req_data.get('action', '').strip()
        mint_address = req_data.get('mint', '').strip()
        amount_input = req_data.get('amount')

        # 1. CARGAMOS LA BILLETERA
        try:
            keypair = Keypair.from_base58_string(priv_key)
            public_key = str(keypair.pubkey())
        except Exception as e:
            return jsonify({"error": "Clave privada inválida."}), 400

        # === EL SECRETO: FORMATO MATEMÁTICO STRICTO ===
        # PumpPortal exige que 'amount' sea un NÚMERO (0.01) para compras
        # Si le enviamos un texto ("0.01"), la API lo rechaza con 400 Bad Request
        if opcion_action == 'buy':
            action = "buy"
            amount = float(amount_input) # <--- CONVERSIÓN OBLIGATORIA A FLOAT
            denominatedInSol = "true"
        else:
            porcentaje = str(amount_input).replace("%", "").strip()
            action = "sell"
            amount = f"{porcentaje}%"
            denominatedInSol = "false"

        # 3. PARÁMETROS EXACTOS
        payload = {
            "publicKey": public_key,
            "action": action,
            "mint": mint_address,
            "denominatedInSol": denominatedInSol,
            "amount": amount,
            "slippage": 15, 
            "priorityFee": 0.0005,
            "pool": "auto"
        }

        # Cabecera para evadir a Cloudflare
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        # 🚀 PETICIÓN A PUMPPORTAL
        # Obligatorio usar json=payload para que mantenga el formato numérico del amount
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local", 
            json=payload,
            headers=headers
        )
        
        if response.status_code != 200:
            return jsonify({"error": f"Error de PumpPortal: {response.text}"}), 400
            
        tx_bytes = response.content

        # 4. Deserializar y Firmar (Idéntico a tu script)
        tx = VersionedTransaction(VersionedTransaction.from_bytes(tx_bytes).message, [keypair])

        # 5. Enviar a Helius (Idéntico a tu script)
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        txPayload = SendVersionedTransaction(tx, config)

        rpc_response = requests.post(
            url=RPC_URL,
            headers={"Content-Type": "application/json"},
            data=txPayload.to_json()
        )
        
        result_json = rpc_response.json()
        
        # Validación de Errores
        if 'error' in result_json:
            error_data = result_json['error']
            err_msg_lower = str(error_data).lower()
            
            if "insufficient funds" in err_msg_lower or "0x1" in err_msg_lower:
                custom_err = "No tienes suficiente SOL en la billetera."
            elif "slippage" in err_msg_lower or "0x11" in err_msg_lower:
                custom_err = "El precio cambió demasiado rápido (Slippage excedido)."
            else:
                custom_err = error_data.get('message', 'Error desconocido en Solana')
            return jsonify({"error": custom_err}), 400
            
        # 6. Éxito
        txSignature = result_json.get('result')
        return jsonify({"signature": txSignature})

    except Exception as e:
        return jsonify({"error": f"Error crítico: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)