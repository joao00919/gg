"""Validação consolidada da interface observável dos vídeos do ZENYX 4.3.18.

Executa sem conectar ao Discord. Verifica os contratos visuais, os 25 comandos,
os botões principais, Configurar Loja, as interações críticas e a proteção global
de modais/selects.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(command: list[str], label: str) -> None:
    print(f"\n=== {label} ===")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> int:
    python = sys.executable
    run(
        [
            python,
            "-m",
            "pytest",
            "-q",
            "tests/test_uploaded_video_complete_contract_4318.py",
            "tests/test_discord_runtime_safety_4318.py",
            "tests/test_full_video_interface_4318.py",
            "tests/test_video_reference_functional_4318.py",
            "tests/test_configurar_loja_video_complete_4318.py",
            "tests/test_ticket_video_complete_4318.py",
        ],
        "Contratos dos vídeos",
    )
    run([python, "VALIDAR_INTERACOES_LOCAL.py"], "Comandos críticos")
    run([python, "VALIDAR_BOTOES_MENU_LOCAL.py"], "Botões do menu")
    run([python, "VALIDAR_CONFIGURAR_LOJA_LOCAL.py"], "Configurar Loja")
    print("\nRESULTADO FINAL: contratos e interações observáveis validados com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
