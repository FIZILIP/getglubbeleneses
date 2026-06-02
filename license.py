"""
GET CLUB - Sistema de Licença
Trial de 3 dias + licenças anual e vitalícia.
"""

import hashlib
import hmac
import json
import os
import platform
import secrets
from datetime import datetime, timedelta

LICENSE_FILE = os.environ.get(
    "GETCLUB_LICENSE_FILE",
    os.path.join(os.path.expanduser("~"), ".getclub_license.json"),
)
SECRET = "GETCLUB_SECRET_2024_XK9"
KEY_PREFIX = "GETCLUB2"
TRIAL_DAYS = 3


def get_machine_id():
    """Gera um ID único baseado na máquina."""
    raw = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16].upper()


def load_license():
    if not os.path.exists(LICENSE_FILE):
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_license(data):
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def init_trial():
    data = {
        "type": "trial",
        "start_date": datetime.now().isoformat(),
        "machine_id": get_machine_id(),
        "activated": False,
        "key": None,
    }
    save_license(data)
    return data


def _sign_payload(payload):
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:10].upper()


def _is_legacy_key_valid(key):
    """Compatibilidade com chaves antigas GETCLUB-XXXX-XXXX-XXXX-CHECKSUM."""
    try:
        parts = key.strip().upper().split("-")
        if len(parts) != 5 or parts[0] != "GETCLUB":
            return False
        payload = "-".join(parts[:4])
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:8].upper()
        return parts[4] == expected
    except Exception:
        return False


def verify_key(key):
    """
    Verifica chave no formato:
    GETCLUB2-TIPO-EXPIRACAO-RANDOM-SIGNATURE
    TIPO: A (anual) ou V (vitalícia)
    EXPIRACAO: YYYYMMDD (anual) ou PERP (vitalícia)
    """
    try:
        normalized = key.strip().upper()
        parts = normalized.split("-")

        if len(parts) == 5 and parts[0] == KEY_PREFIX:
            _, license_type, expiry_token, random_token, signature = parts

            if license_type not in {"A", "V"}:
                return False, "Tipo de licença inválido.", None
            if len(random_token) != 8:
                return False, "Token da licença inválido.", None

            payload = "-".join(parts[:4])
            expected_signature = _sign_payload(payload)
            if signature != expected_signature:
                return False, "Assinatura da chave inválida.", None

            expires_at = None
            if license_type == "A":
                try:
                    expires_at = datetime.strptime(expiry_token, "%Y%m%d")
                except ValueError:
                    return False, "Data da licença anual inválida.", None
            else:
                if expiry_token != "PERP":
                    return False, "Token da licença vitalícia inválido.", None

            details = {
                "license_type": "annual" if license_type == "A" else "lifetime",
                "expires_at": expires_at.isoformat() if expires_at else None,
                "random_token": random_token,
            }
            return True, "Chave válida.", details

        if _is_legacy_key_valid(normalized):
            details = {"license_type": "lifetime", "expires_at": None, "random_token": "LEGACY"}
            return True, "Chave legada válida.", details

        return False, "Formato de chave inválido.", None
    except Exception:
        return False, "Erro ao validar chave.", None


def generate_license_key(license_type="annual", years=1):
    """
    Função utilitária para o gerador:
    - annual: válida por N anos (default 1)
    - lifetime: sem expiração
    """
    ltype = license_type.strip().lower()
    if ltype not in {"annual", "lifetime"}:
        raise ValueError("license_type deve ser 'annual' ou 'lifetime'")

    random_token = secrets.token_hex(4).upper()
    type_token = "A" if ltype == "annual" else "V"
    if ltype == "annual":
        expiry_dt = datetime.now() + timedelta(days=365 * max(1, int(years)))
        expiry_token = expiry_dt.strftime("%Y%m%d")
    else:
        expiry_token = "PERP"

    payload = f"{KEY_PREFIX}-{type_token}-{expiry_token}-{random_token}"
    signature = _sign_payload(payload)
    return f"{payload}-{signature}"


def activate_license(key):
    ok, msg, details = verify_key(key)
    if not ok:
        return False, msg

    data = load_license() or {}
    data["type"] = details["license_type"]
    data["key"] = key.strip().upper()
    data["activated"] = True
    data["activation_date"] = datetime.now().isoformat()
    data["machine_id"] = get_machine_id()
    data["expires_at"] = details.get("expires_at")
    save_license(data)

    if details["license_type"] == "lifetime":
        return True, "Licença vitalícia ativada com sucesso!"
    exp_date = datetime.fromisoformat(details["expires_at"]).strftime("%d/%m/%Y")
    return True, f"Licença anual ativada com sucesso! Válida até {exp_date}."


def check_license():
    """
    Retorna: (status, mensagem, dias_restantes)
    status: 'ok' | 'need_key'
    """
    lic = load_license()
    if lic is None:
        lic = init_trial()

    if lic.get("activated"):
        if lic.get("machine_id") and lic.get("machine_id") != get_machine_id():
            return "need_key", "Licença vinculada a outro equipamento.", 0

        ok, _, details = verify_key(lic.get("key", ""))
        if not ok:
            return "need_key", "Chave de licença inválida. Introduza uma chave válida.", 0

        if details["license_type"] == "lifetime":
            return "ok", "Licença vitalícia ativa.", None

        try:
            expires_at = datetime.fromisoformat(details["expires_at"])
        except Exception:
            return "need_key", "Data de expiração inválida na licença.", 0

        if datetime.now() <= expires_at + timedelta(days=1):
            remaining = (expires_at.date() - datetime.now().date()).days
            return "ok", f"Licença anual ativa. {max(0, remaining)} dia(s) restante(s).", remaining
        return "need_key", "Licença anual expirada. Introduza uma nova chave.", 0

    try:
        start = datetime.fromisoformat(lic["start_date"])
    except Exception:
        lic = init_trial()
        start = datetime.now()

    elapsed = datetime.now() - start
    days_remaining = TRIAL_DAYS - elapsed.days
    if days_remaining > 0:
        return "ok", f"Período de avaliação: {days_remaining} dia(s) restante(s).", days_remaining
    return "need_key", "O período de avaliação expirou. Introduza a sua chave de ativação.", 0
