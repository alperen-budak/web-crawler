.PHONY: build up down logs test shell

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	docker-compose run --rm crawler-app python -m unittest discover -s tests -v

shell:
	docker-compose run --rm crawler-app /bin/sh
