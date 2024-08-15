#!/bin/sh
# run database migrations
python manage.py migrate --no-input
# create the superuser if a password was supplied
if [ ! -z ${DJANGO_SUPERUSER_PASSWORD} ] ; then
  python manage.py createsuperuser --no-input --username=${DJANGO_SUPERUSER_NAME} --email=${DJANGO_SUPERUSER_EMAIL}
fi

# startup with whatever command was provided
"$@"