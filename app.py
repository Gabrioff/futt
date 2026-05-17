import sys
import os
import requests
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig

# --- CONFIGURACIÓN DEL RPC ---
# Usamos el RPC de Helius que proporcionaste para máxima velocidad
RPC_URL = "https://mainnet.helius-rpc.com/?api-key=d644072d-c54e-4f39-afa4-126063e96146"

def main():
    print("\n" + "="*50)
    print("🚀 BOT DE COMPRA RÁPIDA - PUMP.FUN & HELIUS 🚀")
    print("="*50 + "\n")
    
    # 1. Obtener la Clave Privada de forma segura (Local y con guardado)
    KEY_FILE = "private_key.txt"
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            priv_key = f.read().strip()
        print("✅ Clave privada cargada automáticamente desde 'private_key.txt'.")
    else:
        priv_key = input("🔑 Ingresa tu Clave Privada (formato base58): ").strip()
    
    try:
        keypair = Keypair.from_base58_string(priv_key)
        public_key = str(keypair.pubkey())
        print(f"✅ Billetera cargada exitosamente: {public_key}")
        
        # Guardar la clave solo si es válida y no existía el archivo
        if not os.path.exists(KEY_FILE):
            with open(KEY_FILE, "w") as f:
                f.write(priv_key)
            print("💾 Clave privada guardada en 'private_key.txt' para futuras sesiones.\n")
            
    except Exception as e:
        print("❌ Error: Clave privada inválida. Verifica el formato o elimina 'private_key.txt' si hay un error.")
        return

    # 2. Menú de opciones (Comprar o Vender)
    print("\n¿Qué operación deseas realizar?")
    print("1. 🟢 COMPRAR")
    print("2. 🔴 VENDER")
    opcion = input("👉 Elige una opción (1 o 2): ").strip()

    if opcion not in ['1', '2']:
        print("❌ Error: Opción inválida.")
        return

    mint_address = input("\n🪙 Ingresa el Contract Address (CA) del Token: ").strip()

    if opcion == '1':
        # Lógica de COMPRA
        try:
            amount_input = float(input("💰 Cantidad de SOL a invertir: "))
        except ValueError:
            print("❌ Error: Por favor ingresa un número válido para los SOL.")
            return
        action = "buy"
        amount = amount_input
        denominatedInSol = "true"
    else:
        # Lógica de VENTA
        porcentaje = input("📉 Porcentaje de tokens a vender (ej. 100 para vender todo, 50 para la mitad): ").strip()
        porcentaje = porcentaje.replace("%", "") # Limpiamos por si el usuario escribe el símbolo "%"
        
        # Validar que el valor ingresado tenga sentido
        if not porcentaje.replace(".", "").isnumeric():
            print("❌ Error: Ingresa un porcentaje válido (solo números).")
            return
            
        action = "sell"
        amount = f"{porcentaje}%"
        denominatedInSol = "false" # "false" le indica a la API que el monto es de tokens, no de SOL

    # 3. Configurar los parámetros de PumpPortal
    # priorityFee: 0.0005 SOL (subido ligerísimamente para igualar el formato de la doc y evitar conflictos)
    # slippage: 15% es recomendado para Pump.fun
    # pool: "auto" (Recomendado por la doc. Funciona si está en pump.fun o si ya migró a Raydium)
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

    print(f"\n⏳ 1/3 Solicitando transacción de {action.upper()} a PumpPortal...")
    try:
        # Petición a PumpPortal (Cambiado 'json=' por 'data=' según la documentación oficial de Python)
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local", 
            data=payload
        )
        
        if response.status_code != 200:
            print(f"❌ Error de PumpPortal: {response.status_code} - {response.text}")
            print("👉 Revisa que el Contract Address (CA) esté bien escrito y no tenga espacios extra.")
            return
            
        tx_bytes = response.content
        print("✅ Transacción generada.")
    except Exception as e:
        print(f"❌ Error de conexión con PumpPortal: {e}")
        return

    # 4. Deserializar y Firmar la transacción localmente
    print("⏳ 2/3 Firmando la transacción localmente...")
    try:
        # EXACTAMENTE como en la documentación oficial:
        tx = VersionedTransaction(VersionedTransaction.from_bytes(tx_bytes).message, [keypair])
        print("✅ Transacción firmada.")
    except Exception as e:
        print(f"❌ Error al firmar la transacción: {e}")
        return

    # 5. Enviar la transacción a la blockchain (MÉTODO OFICIAL DE LA DOC)
    print("⏳ 3/3 Enviando a la red (Helius RPC)...")
    try:
        # Configuramos el commitment como indica la guía
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        
        # Preparamos el payload exacto para el RPC de Solana
        txPayload = SendVersionedTransaction(tx, config)

        # Hacemos el POST directo al RPC de Helius
        rpc_response = requests.post(
            url=RPC_URL,
            headers={"Content-Type": "application/json"},
            data=txPayload.to_json()
        )
        
        result_json = rpc_response.json()
        
        # Validar si hubo un error real de Solana
        if 'error' in result_json:
            print("\n" + "="*50)
            print("❌ LA RED DE SOLANA RECHAZÓ LA TRANSACCIÓN ❌")
            error_data = result_json['error']
            print(f"Código de error: {error_data.get('code')}")
            print(f"Mensaje: {error_data.get('message')}")
            
            # Analizar el error para darte pistas útiles
            err_msg_lower = str(error_data).lower()
            if "insufficient funds" in err_msg_lower or "0x1" in err_msg_lower:
                print("👉 Causa Probable: No tienes suficiente SOL en la billetera.")
                print("   Asegúrate de tener un extra para el Rent (~0.002 SOL) y Fees.")
            elif "slippage" in err_msg_lower or "0x11" in err_msg_lower:
                print("👉 Causa Probable: El precio cambió demasiado rápido (Slippage excedido).")
            print("="*50)
            
        else:
            txSignature = result_json['result']
            print("\n" + "="*50)
            print("🎉 ¡TRANSACCIÓN ACEPTADA Y ENVIADA! 🎉")
            print(f"Firma (Signature): {txSignature}")
            print(f"🔍 Verifica tu compra en Solscan:")
            print(f"👉 https://solscan.io/tx/{txSignature}")
            print("="*50)

    except Exception as e:
        print(f"\n❌ Error crítico al enviar la petición al RPC: {e}")

if __name__ == "__main__":
    main()