CC = cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic -O2

build/minidb: src/db.c
	mkdir -p build
	$(CC) $(CFLAGS) src/db.c -o build/minidb

test: build/minidb
	python3 tests/test_db.py

.PHONY: test
