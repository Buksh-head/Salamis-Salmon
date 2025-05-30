import json
import threading
import time
import serial
from web3 import Web3
from influxdb_client import InfluxDBClient, Point
from datetime import datetime, timezone

# --- Blockchain Setup ---
web3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
account = web3.eth.account.from_key(private_key)
wallet_address = account.address
 
abi = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": False,
                "internalType": "string",
                "name": "nodeId",
                "type": "string"
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "temp",
                "type": "int256"
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "hum",
                "type": "int256"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "gas",
                "type": "uint256"
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "acc_int",
                "type": "int256"
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "acc_dec",
                "type": "int256"
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "lat",
                "type": "int256"
            },
            {
                "indexed": False,
                "internalType": "int256",
                "name": "lon",
                "type": "int256"
            }
        ],
        "name": "DataLogged",
        "type": "event"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "index",
                "type": "uint256"
            }
        ],
        "name": "getRecord",
        "outputs": [
            {
                "internalType": "string",
                "name": "",
                "type": "string"
            },
            {
                "internalType": "int256",
                "name": "",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "",
                "type": "int256"
            },
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            },
            {
                "internalType": "int256",
                "name": "",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "",
                "type": "int256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getRecordCount",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "string",
                "name": "nodeId",
                "type": "string"
            },
            {
                "internalType": "int256",
                "name": "temp",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "hum",
                "type": "int256"
            },
            {
                "internalType": "uint256",
                "name": "gas",
                "type": "uint256"
            },
            {
                "internalType": "int256",
                "name": "acc_int",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "acc_dec",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "lat",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "lon",
                "type": "int256"
            }
        ],
        "name": "logData",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "name": "records",
        "outputs": [
            {
                "internalType": "string",
                "name": "nodeId",
                "type": "string"
            },
            {
                "internalType": "int256",
                "name": "temp",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "hum",
                "type": "int256"
            },
            {
                "internalType": "uint256",
                "name": "gas",
                "type": "uint256"
            },
            {
                "internalType": "int256",
                "name": "acc_int",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "acc_dec",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "lat",
                "type": "int256"
            },
            {
                "internalType": "int256",
                "name": "lon",
                "type": "int256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

#contract_address = "0x0B306BF915C4d645ff596e518fAf3F9669b97016"
#contract_address = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
contract_address = "0x5FbDB2315678afecb367f032d93F642f64180aa3"   #FROM TERMINAL call
contract = web3.eth.contract(address=contract_address, abi=abi)


# --- InfluxDB Setup ---
influx_url = "http://localhost:8086"
influx_token = "CDcS5szhZObalII0i-MlHIq3vmdgbadXPXBCkN_c41QBzckAwTZ0KiMrRIaVYm1seJVL-Rcapjm9CjMb7CrByw=="
#influx_token = "gZczdiLi_tImJS2h-5VIrUF7zvS8ECPQbzzvzFbqCvCaJdT9XJBhC8bvCbPtYKtjvJkBb0-OomKflwnRBOVkJw==e"
influx_org = "uq"
influx_bucket = "project"
client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
write_api = client.write_api()
 
ser = serial.Serial("COM9", 115200, timeout=1)  


usb_file_path = "E:\.txt"   

def save_to_usb(data_str):
    with open(usb_file_path, "a") as f: 
        f.write(data_str + "\n")

def parse_and_send_serial_data():
    while True:
        try:
            # fake_data = {
            #     "temp": 23.45,
            #     "hum": 56.78,
            #     "gas": 0.123,
            #     "acc": 9.81,
            #     "lat": -27.467,
            #     "lon": 153.027
            # }
            # fake_json = json.dumps(fake_data)
            raw = ser.readline().decode("utf-8").strip()
            
    #    raw = fake_json 
            if not raw:
                continue

            print("Received UART:", raw)
            data = json.loads(raw)
            save_to_usb(raw)

            # Extract and scale values
            nodeId = str(data["id"])
            temp = int(data["temp"] * 100)
            hum = int(data["hum"] * 1000)
            gas = int(data["gas"] * 10000)
            acc = float(data["acc"])  # Convert to float first
            acc_int = int(acc * 1000)
            acc_dec = int((acc % 1) * 1000)
            lat = int(float(data["lat"]) * 1e6)
            lon = int(float(data["lon"]) * 1e6)

            # Build transaction
            tx = contract.functions.logData(
                nodeId, temp, hum, gas, acc_int, acc_dec, lat, lon
            ).build_transaction({
                'from': wallet_address,
                'nonce': web3.eth.get_transaction_count(wallet_address),
                'gas': 500000,
                'gasPrice': web3.to_wei('10', 'gwei')
            })

            signed_tx = web3.eth.account.sign_transaction(tx, private_key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print("Blockchain TX:", tx_hash.hex())
  

       ##     print(web3.eth.get_balance(wallet_address))
           

        except json.JSONDecodeError:
            print("Malformed JSON, skipping")
        except Exception as e:
            print("Error:", e)

# def fetch_and_send():
#     try:
#         record_count = contract.functions.getRecordCount().call()
#         print(f"Found {record_count} records in contract")

#         for i in range(record_count):
#             record = contract.functions.getRecord(i).call()
        
#             nodeId, temp, hum, gas, acc_int, acc_dec, lat, lon = record
            
#             point = (
#                 Point("environmental_data")
#                 .tag("id", nodeId)
#                 .field("temp", temp)
#                 .field("hum", hum)
#                 .field("gas", gas) 
#                 .field("lat", lat)
#                 .field("lon", lon)
#                  .time(datetime.now(timezone.utc))
#             )
 
#             write_api.write(bucket=influx_bucket, org=influx_org, record=point)
#         #    print(f"Written record {i} to InfluxDB")

                       
    
    # except Exception as e:
    #     print("Error:", e)


def fetch_and_send():
    try:
        record_count = contract.functions.getRecordCount().call()
        print(f"Found {record_count} records in contract")

        for i in range(record_count):
            record = contract.functions.getRecord(i).call()
            nodeId, temp, hum, gas, acc_int, acc_dec, lat, lon = record
 
            node_id = str(nodeId)
 
            points = [
                {
                    "measurement": "environmental_data",
                    "tags": {
                        "id": node_id,
                        "sensor": "temp"
                    },
                    "fields": {
                        "value": float(temp)
                    },
                    "time": datetime.now(timezone.utc).isoformat()
                },
                {
                    "measurement": "environmental_data",
                    "tags": {
                        "id": node_id,
                        "sensor": "hum"
                    },
                    "fields": {
                        "value": float(hum)
                    },
                    "time": datetime.now(timezone.utc).isoformat()
                },
                {
                    "measurement": "environmental_data",
                    "tags": {
                        "id": node_id,
                        "sensor": "gas"
                    },
                    "fields": {
                        "value": float(gas)
                    },
                    "time": datetime.now(timezone.utc).isoformat()
                },
              
            ]
 
            write_api.write(bucket=influx_bucket, org=influx_org, record=points)
         #   print(f"Written record {i} for node {node_id} to InfluxDB")

    except Exception as e:
        print(f"Error fetching or sending data: {e}")

def periodic_fetch():
    while True:
        fetch_and_send()
        time.sleep(5)

if __name__ == "__main__":

    fetch_thread = threading.Thread(target=periodic_fetch, daemon=True)
    fetch_thread.start()
    try:
        print("waiting for base node data")
        parse_and_send_serial_data()
    except KeyboardInterrupt:
        print("Stopping")
    finally:
        write_api.flush()
        client.close()
        ser.close()
