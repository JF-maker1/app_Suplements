# ==========================================
# STAGE 1: BUILDER (Compilation Layer)
# Base: Full Python (obsahuje GCC, Make, headers) - nutné pro kompilaci knihoven
# ==========================================
FROM python:3.13 as builder

WORKDIR /app

# 1. Environment: Vynucení user-space instalace pro snadné kopírování
ENV PYTHONUSERBASE=/root/.local \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 2. Install Dependencies
COPY requirements.txt .
# --user flag nainstaluje balíčky do /root/.local
# --no-cache-dir zajistí, že si neuložíme stažené .whl soubory
RUN pip install --user --no-cache-dir -r requirements.txt

# ==========================================
# STAGE 2: FINAL (Runtime Layer)
# Base: Slim Python (Minimal footprint) - pouze pro běh
# ==========================================
FROM python:3.13-slim

WORKDIR /app

# 3. Environment: Nastavení PATH pro importy z .local
# Musíme systému říct, kde hledat balíčky zkopírované z builderu
ENV PYTHONUSERBASE=/root/.local \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH"

# 4. Copy Artifacts (Závislosti z Builderu)
# Kritický krok: Přenášíme pouze zkompilované knihovny, ne kompilátory
COPY --from=builder /root/.local /root/.local

# 5. Copy Application Code
# Kopírujeme až nakonec, abychom využili Docker cache pro vrstvy výše
COPY . .

# 6. Runtime Metadata
EXPOSE 8000

# Spuštění aplikace
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]