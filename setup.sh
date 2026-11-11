#!/usr/bin/env bash
# Installs EnergyPlus 23.2.0 and Sinergym for the real-environment pipeline.
# The mock pipeline works without this; only run when you want full simulation.
set -euo pipefail

EP_VERSION="23.2.0"
EP_TAG="v23.2.0"
EP_HASH="7636e6b3e9"
EP_INSTALL_DIR="/usr/local/EnergyPlus-23-2-0"
EP_INSTALLER="EnergyPlus-${EP_VERSION}-${EP_HASH}-Linux-Ubuntu22.04-x86_64.sh"

if [[ ! -d "${EP_INSTALL_DIR}" ]]; then
    echo "[setup] Downloading EnergyPlus ${EP_VERSION}..."
    wget -q "https://github.com/NREL/EnergyPlus/releases/download/${EP_TAG}/${EP_INSTALLER}"
    chmod +x "${EP_INSTALLER}"
    echo "[setup] Installing to ${EP_INSTALL_DIR} (needs sudo)..."
    sudo ./"${EP_INSTALLER}" --skip-license --prefix="${EP_INSTALL_DIR}" <<< "y"
    rm "${EP_INSTALLER}"
else
    echo "[setup] EnergyPlus already at ${EP_INSTALL_DIR}, skipping."
fi

export EPLUS_PATH="${EP_INSTALL_DIR}"
echo "export EPLUS_PATH=${EP_INSTALL_DIR}" >> ~/.bashrc

echo "[setup] Installing Python deps..."
pip install -r requirements.txt
pip install sinergym==3.5.7

echo "[setup] Done. Verifying..."
python -c "import sinergym; import gymnasium as gym; \
    env = gym.make('Eplus-5zone-hot-continuous-v1'); \
    print('Sinergym OK, obs shape:', env.observation_space.shape); env.close()"
