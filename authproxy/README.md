## How?

```bash
docker build . -t authproxy
docker run --name=authproxy -e 'DJANGO_ALLOWED_HOSTS=*' -e 'DJANGO_SECRET_KEY=supersecret' -v data:/data/ -p 8000:8000 authproxy
docker exec -it authproxy python manage.py createsuperuser
```

If you encounter a permissions error, ensure that the `www-data:www-data` user (with `uid/gid 82/82`) has permissions to write the volume.

Afterwards visit `http://localhost:8000/admin` to login.
Everything should be self-explanatory.
