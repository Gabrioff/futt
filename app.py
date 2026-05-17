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

# RPC de Helius para máxima velocidad
RPC_URL = "https://mainnet.helius-rpc.com/?api-key=d644072d-c54e-4f39-afa4-126063e96146"

@app.route('/', methods=['GET'])
def home():
    return "🚀 VELOCE RENDER SERVER IS RUNNING"

@app.route('/api/build-tx', methods=['POST'])
def build_tx():
    try:
        # Extraemos los datos que nos envía la extensión (background.js)
        req_data = request.get_json(force=True)
        priv_key = req_data.get('privateKey', '').strip()
        opcion_action = req_data.get('action', '').strip().lower()
        mint_address = req_data.get('mint', '').strip()
        amount_input = req_data.get('amount')

        if not priv_key or not mint_address or not amount_input:
            return jsonify({"error": "Faltan datos obligatorios (privateKey, mint, amount)."}), 400

        # 1. CARGAR LA BILLETERA
        try:
            keypair = Keypair.from_base58_string(priv_key)
            public_key = str(keypair.pubkey())
        except Exception as e:
            return jsonify({"error": "Clave privada inválida."}), 400

        # 2. LÓGICA DE COMPRA / VENTA (Idéntica a pump_buyer.py)
        if opcion_action == 'buy':
            action = "buy"
            try:
                amount = float(amount_input)
            except ValueError:
                return jsonify({"error": "Para comprar, la cantidad de SOL debe ser un número válido."}), 400
            denominatedInSol = "true"
            
        elif opcion_action == 'sell':
            action = "sell"
            porcentaje = str(amount_input).replace("%", "").strip()
            
            # Validar que el porcentaje sea numérico
            if not porcentaje.replace(".", "").isnumeric():
                return jsonify({"error": "Porcentaje de venta inválido."}), 400
                
            amount = f"{porcentaje}%"
            denominatedInSol = "false"
            
        else:
            return jsonify({"error": "Acción inválida. Utiliza 'buy' o 'sell'."}), 400

        # 3. CONFIGURAR LOS PARÁMETROS DE PUMPPORTAL
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

        # 🚀 PETICIÓN A PUMPPORTAL
        try:
            # Utilizamos data=payload como indica tu script original que funcionaba bien
            response = requests.post(
                url="https://pumpportal.fun/api/trade-local", 
                data=payload
            )
            
            if response.status_code != 200:
                return jsonify({"error": f"Error de PumpPortal: {response.text}"}), 400
                
            tx_bytes = response.content
        except Exception as e:
            return jsonify({"error": f"Error de conexión con PumpPortal: {str(e)}"}), 500

        # 4. DESERIALIZAR Y FIRMAR LA TRANSACCIÓN
        try:
            tx = VersionedTransaction(VersionedTransaction.from_bytes(tx_bytes).message, [keypair])
        except Exception as e:
            return jsonify({"error": f"Error al firmar la transacción: {str(e)}"}), 500

        # 5. ENVIAR LA TRANSACCIÓN A HELIUS
        try:
            commitment = CommitmentLevel.Confirmed
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            txPayload = SendVersionedTransaction(tx, config)

            rpc_response = requests.post(
                url=RPC_URL,
                headers={"Content-Type": "application/json"},
                data=txPayload.to_json()
            )
            
            result_json = rpc_response.json()
            
            # Validación de Errores detallada (Idéntico al bot local)
            if 'error' in result_json:
                error_data = result_json['error']
                err_msg_lower = str(error_data).lower()
                
                if "insufficient funds" in err_msg_lower or "0x1" in err_msg_lower:
                    custom_err = "No tienes suficiente SOL. Asegúrate de tener para el Rent (~0.002 SOL) y Fees."
                elif "slippage" in err_msg_lower or "0x11" in err_msg_lower:
                    custom_err = "El precio cambió demasiado rápido (Slippage excedido)."
                else:
                    custom_err = f"La red rechazó la tx: {error_data.get('message')}"
                    
                return jsonify({"error": custom_err}), 400
                
            # 6. ÉXITO 🎉
            txSignature = result_json.get('result')
            return jsonify({"signature": txSignature, "success": True})
            
        except Exception as e:
            return jsonify({"error": f"Error crítico al enviar al RPC: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Error general del servidor: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)