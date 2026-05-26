#!/usr/bin/env python3
import os
import fcntl
import sys
import time

# ID do HUB usado (Obtidos após o ID do hub com 'lsusb')
HUB_VENDOR = "214b"
HUB_PRODUCT = "7250"

# ID das ESPs (CP2102)
ESP_VENDOR = "10c4"
ESP_PRODUCT = "ea60"

# Código de Reset USB no Linux
USBDEVFS_RESET = 21780

def find_devices_by_id(target_vid, target_pid):
    # Caminho base dos dispositivos USB no Linux
    base = "/sys/bus/usb/devices"
    found_devices = []
    
    if not os.path.exists(base):
        return found_devices

    # Varre a pasta de dispositivos do sistema
    for device in os.listdir(base):
        if not device[0].isdigit(): continue # Ignora root hubs
            
        vid_path = os.path.join(base, device, "idVendor")
        pid_path = os.path.join(base, device, "idProduct")
        
        if os.path.exists(vid_path) and os.path.exists(pid_path):
            try:
                with open(vid_path, 'r') as f: vid = f.read().strip()
                with open(pid_path, 'r') as f: pid = f.read().strip()
                
                if vid == target_vid and pid == target_pid:
                    # Reconstrói o caminho do dispositivo (/dev/bus/usb/BBB/DDD)
                    bus_path = os.path.join(base, device, "busnum")
                    dev_path = os.path.join(base, device, "devnum")
                    
                    with open(bus_path, 'r') as f: bus = f.read().strip()
                    with open(dev_path, 'r') as f: dev = f.read().strip()
                    
                    full_path = f"/dev/bus/usb/{bus.zfill(3)}/{dev.zfill(3)}"
                    found_devices.append(full_path)
            except:
                continue
    return found_devices

def reset_usb_device(dev_path):
    try:
        with open(dev_path, 'w', os.O_WRONLY) as f:
            fcntl.ioctl(f, USBDEVFS_RESET, 0)
            return True
    except Exception as e:
        print(f" [Erro: {e}]", end='')
        return False

def sequential_reset():
    print("--- 1. RESET DO HUB PRINCIPAL ---")
    print("Verificar se o hub está na usb correta: inferior esquerda da Jetson")
    hubs = find_devices_by_id(HUB_VENDOR, HUB_PRODUCT)
    
    if not hubs:
        print(f"[AVISO] Hub {HUB_VENDOR}:{HUB_PRODUCT} não encontrado! Pulando para ESPs...")
    else:
        for hub in hubs:
            print(f"Resetando Hub em {hub} ... ", end='')
            if reset_usb_device(hub):
                print("[OK]")
            else:
                print("[FALHA]")
        
        print("\n>>> Aguardando 2 segundos para re-enumeração das ESPs <<<")
        time.sleep(2)

    print("\n--- 2. RESET INDIVIDUAL DAS ESPs ---")
    # Buscamos as ESPs agora
    esps = find_devices_by_id(ESP_VENDOR, ESP_PRODUCT)
    
    if not esps:
        print("[ERRO CRÍTICO] Nenhuma ESP detectada após reset do Hub.")
        print("DICA: Verifique cabos ou aumente o tempo de sleep no script.")
    else:
        for i, esp in enumerate(esps):
            print(f"Resetando ESP #{i+1} em {esp} ... ", end='')
            sys.stdout.flush()
            if reset_usb_device(esp):
                print("[OK]")
            else:
                print("[FALHA]")
            # Pequena pausa entre ESPs para evitar pico de corrente simultâneo
            time.sleep(0.5) 

    print("\n--- Ciclo Completo ---")

if __name__ == "__main__":
    sequential_reset()