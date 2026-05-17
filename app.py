from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig

app = Flask(__name__)
# Palubosan dagiti kiddaw manipud Chrome
CORS(app)

RPC_URL = "https://mainnet.helius-rpc.com/?api-key=d644072d-c54e-4f39-afa4-126063e96146"

@app.route('/', methods=['GET'])
def home():
    return "⚡ Veloce Pro FULL PYTHON API ket AKTIBO"

@app.route('/api/build-tx', methods=['POST'])
def build_tx():
    try:
        req_data = request.json
        priv_key = req_data.get('privateKey')
        action = req_data.get('action')
        mint = req_data.get('mint')
        amount = req_data.get('amount')

        try:
            keypair = Keypair.from_base58_string(priv_key)
            public_key = str(keypair.pubkey())
        except Exception as e:
            return jsonify({"error": "Imbalido a pribado a tulbek."}), 400

        denominated_in_sol = "true" if action == "buy" else "false"

        payload = {
            "publicKey": public_key,
            "action": action,
            "mint": mint,
            "amount": amount,
            "denominatedInSol": denominated_in_sol,
            "slippage": 15,
            "priorityFee": 0.0005,
            "pool": "auto"
        }
        
        # 🚀 SOLUCIÓN ANTI-BOTS PARA SALTAR EL FIREWALL DE CLOUDFLARE
        # Nos disfrazamos de Google Chrome para que no rechacen a Hugging Face
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Usamos json=payload junto con las cabeceras disfrazadas
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local", 
            headers=headers,
            json=payload
        )
        
        # Imprimimos el error real en la consola por si acaso
        print(f"Respuesta PumpPortal: {response.status_code} - {response.text}")
        
        if response.status_code != 200:
            return jsonify({"error": f"Biddut API PumpPortal: {response.text}"}), 400

        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [keypair])

        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        
        rpc_response = requests.post(
            url=RPC_URL,
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(tx, config).to_json()
        )
        
        result_json = rpc_response.json()
        
        if 'error' in result_json:
            error_data = result_json['error']
            err_msg_lower = str(error_data).lower()
            
            custom_err = error_data.get('message', 'Di am-ammo a biddut iti Solana')
            if "insufficient funds" in err_msg_lower or "0x1" in err_msg_lower:
                custom_err = "Awan ti umdas a SOL iti pitakam tapno mabayadan ti panaggatang ken bayad."
            elif "slippage" in err_msg_lower or "0x11" in err_msg_lower:
                custom_err = "Pardas unay a nagbaliw ti presyo (Slippage excedido)."
                
            return jsonify({"error": custom_err}), 400
            
        tx_signature = result_json.get('result')
        return jsonify({"signature": tx_signature})

    except Exception as e:
        return jsonify({"error": f"Biddut ti server a Python: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)