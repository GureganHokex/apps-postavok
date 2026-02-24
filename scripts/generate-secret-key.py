#!/usr/bin/env python3
"""
Генератор безопасного секретного ключа для Django.
"""
import secrets
import string

def generate_secret_key():
    """Генерирует безопасный секретный ключ для Django."""
    chars = string.ascii_letters + string.digits + string.punctuation
    # Убираем символы, которые могут вызвать проблемы в .env файле
    chars = chars.replace("'", "").replace('"', '').replace('\\', '').replace('$', '')
    return ''.join(secrets.choice(chars) for _ in range(50))

if __name__ == '__main__':
    print(generate_secret_key())
