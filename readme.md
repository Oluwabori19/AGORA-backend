# 🚀 AGORA Development Environment – Full Setup Guide

This guide is designed for new developers joining the AGORA project. It covers setting up the Python backend, dependency management, building API and GeoServer containers, and running everything with Docker Compose in both dev and production modes.

---

## 📚 1. Python API & Dependency Management

AGORA's API is based on Python 3.10 using **Poetry** and **Conda** for dependency management.

### 📦 Poetry (Recommended)

```bash
poetry add --lock package_name
poetry update
```

* Automatically updates `pyproject.toml` and `poetry.lock`

### 🐍 Conda (for system-level or pip-incompatible packages)

```bash
conda install some_package=version
conda env export --from-history > environment.yml
conda-lock -f environment.yml --lockfile conda-lock.yml
```

> Always run the image update script after changes:

```bash
./src/docker-python-env/create_docker_image.sh
```

---

## 🧱 2. How the `agora-api-image:latest` is Created

### 🔁 Automatic Image Update Script

**Path:**

```bash
./src/docker-python-env/create_docker_image.sh
```

**Logic:**

```bash
if git diff --exit-code pyproject.toml environment.yml; then
  echo "No changes in dependencies. Skipping image update."
  exit 0
else
  docker commit agora-dev-api agora-api-image:latest
fi
```

This script ensures that the Docker image is updated only when library dependencies change. All developers and CI pipelines should use this.

---

## 🌍 3. GeoServer Container Setup

AGORA uses a modular GeoServer build system with plugin support and custom CORS configuration.

### 📁 Structure

```
geoserver_agora/
├── plugins/                  # Plugin jars
├── Dockerfile                # Final image using base + plugins
├── download_plugins.sh

geoserver_base/
├── Dockerfile                # Base image
├── entrypoint.sh             # Startup logic
├── production_web.xml        # CORS etc.
├── set_geoserver_auth.sh     # Admin credentials
├── tasks.py                  # (Optional)
```

### 🏗 1. Build Base Image

```bash
cd geoserver_base/
docker build -t dcs-base-geoserver:2.27.6 .
```

### 📦 2. Download Plugins

```bash
cd geoserver_agora/
chmod +x download_plugins.sh
./download_plugins.sh "2.27.6" "mbstyle vectortiles"
```

> ⚠️ Warning: `plugins/` will be wiped before downloading.

### 🚀 3. Build AGORA GeoServer Image

```bash
docker build . -t agora-geoserver:2.27.6
```

---

## 🐳 4. Dev Image: Building & Running

To build and run the full dev environment:

```bash
chmod +x build_dev_container.sh
./build_dev_container.sh
```

Which runs:

```bash
docker compose -f docker-compose-dev.yml --env-file src/app/.env up -d --build
```

### ⚠️ Reminder

If you make any changes to dependencies in the API (`pyproject.toml` or `environment.yml`), you must run:

```bash
./src/docker-python-env/create_docker_image.sh
```

This ensures the dev image reflects those changes.

---

## ⚙️ 5. Docker Compose (Dev & Prod)

### 🔧 Dev Mode

```bash
docker compose -f docker-compose-dev.yml --env-file src/app/.env up -d
```

### 🚀 Production Mode

```bash
docker compose -f docker-compose-prod.yml --env-file src/app/.env up -d
```

### 📁 Example `.env`

> 📌 **Note:** The `.env` file must be located at:
>
> ```
> src/app/.env
> ```
>
> This path is used by both `docker-compose-dev.yml` and `docker-compose-prod.yml`. A template is available at:
>
> ```
> src/app/.env.example
> ```

> ⚠️ **GeoServer Notice:**
> Environment variables such as `GEOSERVER_ADMIN_USER` and `GEOSERVER_ADMIN_PASSWORD` **are used** by the GeoServer container **only if declared in your docker-compose file.**
> However, CORS-related settings (like `GEOSERVER_CORS_ALLOWED_ORIGINS`, etc.) must be set manually in `geoserver_base/Dockerfile` and rebuilt accordingly.

```env
DATABASE_HOSTNAME=db
DATABASE_PORT=5432
DATABASE_NAME=agora
DATABASE_USERNAME=agora
DATABASE_PASSWORD=agora

SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=760
REFRESH_TOKEN_EXPIRE_MINUTES=1000

GEOSERVER_ADMIN_USER=admin
GEOSERVER_ADMIN_PASSWORD=geoserver2
GEOSERVER_PORT=8383
GEOSERVER_CORS_ENABLED=True
GEOSERVER_CORS_ALLOWED_ORIGINS=*
GEOSERVER_CORS_ALLOWED_METHODS=GET,POST,PUT,DELETE,HEAD,OPTIONS
GEOSERVER_CORS_ALLOWED_HEADERS=*
GEOSERVER_CSRF_DISABLED=true
```

---

## 📁 6. API Code Structure

```
app/
├── auth/         # Login, Register, Token
├── db/           # SQLAlchemy + GeoAlchemy2 models
├── geoserver/    # GeoServer REST API integration
├── ligfinder/    # Spatial analysis module
├── utils/        # Shared helpers
└── main.py       # FastAPI entry point
```

---

## 🧪 7. Dev Utilities

* Enter API container:

```bash
docker exec -it agora-dev-api bash
```

* Restart only the API:

```bash
docker compose restart api
```

* Tail logs:

```bash
docker logs -f agora-dev-api
```

---

## ✅ 8. Production Deployment Note

In production, the API container directly mounts the `src/` directory from the main repository.

> **To reflect new changes, you must log into the production server and run:**
>
> ```bash
> git pull
> ```
>
> This ensures the latest codebase is updated inside the container.
> Since the container uses the mounted `src/` folder directly, no rebuild is required after pulling updates. Just make sure to test changes in dev before pushing to production.

---

## 💾 9. PostgreSQL Backup & Restore

This section explains how to take backups from **production** and restore them on **development**. This is the preferred way to replicate the live environment locally.

### 🔄 Recommended Workflow (from production → dev)

#### 1. Take a Backup on Production Server (Tar Format)

If a volume is mounted like:

```yaml
volumes:
  - ./database/dumps:/var/lib/postgresql/dumps
```

Then simply run:

```bash
docker exec -it agora-dev-db bash -c "pg_dump -U agora -F t -f /var/lib/postgresql/dumps/dump-$(date +%Y%m%d%H%M).tar agora"
```

> This creates a file like `dump-202506241446.tar` inside `./database/dumps` on host.

If you **do not mount a volume**, you must copy the file manually:

```bash
docker cp agora-dev-db:/tmp/dump.tar ./dump-202506241446.tar
```

#### ⚠️ Important: GUI Tool Notes (e.g., DBeaver)

You can use GUI tools like **DBeaver** for backup and restore **only if you also use the same tool for both actions**. That means:

* If you **export via DBeaver**, you must **import again via DBeaver GUI**.
* Do **not** mix GUI-generated exports with CLI tools like `pg_restore`.

Incompatibilities may otherwise occur, such as:

* `pg_restore: error: unsupported version (1.16) in file header`
* `ERROR: unrecognized configuration parameter "transaction_timeout"`

✅ **Preferred: use `pg_dump` and `pg_restore` directly inside containers**.

---

#### 2. Restore into Dev DB

Preferred approach if volume is already mounted:

```yaml
volumes:
  - ./database/dumps:/var/lib/postgresql/dumps
```

Then place your backup file under `./database/dumps/` and run:

```bash
docker exec -it agora-dev-db bash -c "PGPASSWORD='agora' pg_restore -U agora -h localhost -p 5432 -d agora -c -v /var/lib/postgresql/dumps/dump-202506241446.tar"
```

Alternative if no volume is mounted:

```bash
docker cp ./dump-202506241446.tar agora-dev-db:/tmp/dump.tar

docker exec -it agora-dev-db bash -c "PGPASSWORD='agora' pg_restore -U agora -h localhost -p 5432 -d agora -c -v /tmp/dump.tar"
```


---


# 10. Restore & Backup geoserver

1. `sh backup_geoserver.sh CONTAINER_NAME` (e.g. `sh backup_geoserver.sh agora-geoserver-dev-container`) to create a backup of the geoserver data. This creates a tar.gz of all relevant geoserver content in the geoserver_backup folder
2. `sh restore_geoserver CONTAINER_NAME FILENAME` (e.g. `sh restore_geoserver agora-geoserver-dev-container geoserver-backup-20251217_143039`, filename of bakcup tar without extensions!) to restore the content of the geoserver 
