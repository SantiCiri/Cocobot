import os
from dotenv import load_dotenv
from time import sleep
import random
from datetime import datetime as dt
import pexpect
import logging
import subprocess
import glob

#Eliminar todos los archivos que terminen en .log
#[os.remove(f) for f in glob.glob("*.log")]

logging.basicConfig(filename='logs.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Cargar variables de entorno del archivo .env
load_dotenv('/home/santiago/Desktop/cocos/.env')

def windscribe_login(username, password):
    logging.info('Iniciando el proceso de login en Windscribe.')
    # Inicia el proceso windscribe login
    process = pexpect.spawn('windscribe login')
    sleep(1)
    # Espera que aparezca la solicitud de nombre de usuario
    process.expect('Windscribe Username:')
    # Envía el nombre de usuario
    process.sendline(username)
    logging.info('Nombre de usuario enviado.')
    sleep(1)
    # Espera que aparezca la solicitud de contraseña
    process.expect('Windscribe Password:')
    sleep(1)
    # Envía la contraseña
    process.sendline(password)
    logging.info('Contraseña enviada.')
    sleep(1)
    # Espera a que termine el proceso
    process.expect(pexpect.EOF)
    output = process.before.decode('utf-8')
    logging.info(f'Login completado. Output: {output}')

windscribe_login("santiagociri", os.getenv('CLAVE_SECRETA_COCOS'))

# list of VPN server codes
codeList = ["US-C", "US", "US-W", "CA", "CA-W",
            "FR", "DE", "NL", "NO", "RO", "CH", "GB", "HK"]

try: 
    while 11 <= dt.now().hour < 17:
        choiceCode = random.choice(codeList)
        os.system(f"windscribe connect {choiceCode}")
        logging.info(f'Conectando a Windscribe VPN servidor: {choiceCode}')

        processes = []
        for strategy in ["operar_MR36O_LECHO","operar_TX26_TX28", "operar_pase","operar_precios","operar_TZX26_TZXM6"]:
            # Construir el comando para ejecutar cada script
            command = f"cd /home/santiago/Desktop/cocos && source .venv/bin/activate && python {strategy}.py"
            # Usar subprocess para ejecutar el comando en un proceso independiente
            process = subprocess.Popen(command, shell=True, executable="/bin/bash")
            # Guardar el proceso en la lista
            processes.append(process)
            logging.info(f'Ejecutada la estrategia: {strategy}')
            sleep(2)

        # Terminar los procesos después de una hora y cambiar el IP
        sleep(60*60)

        for process in processes:
            process.terminate()
            process.wait()  # Esperar a que el proceso termine

        os.system("windscribe disconnect")
        logging.info('Desconexión de Windscribe completada.')
        sleep(5)

except Exception as e: logging.error(f'Error principal: {e}')

sleep(5)
os.system("windscribe logout")
logging.info('Sesión cerrada de Windscribe.')