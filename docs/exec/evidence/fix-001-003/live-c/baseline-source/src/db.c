#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_ROWS 100
#define NAME_BYTES 32
#define DB_FILE "data.db"

typedef struct { uint32_t id; char name[NAME_BYTES]; } Row;
typedef struct { Row rows[MAX_ROWS]; uint32_t count; } Table;

static void encode32(unsigned char b[4], uint32_t n) {
    for (unsigned i = 0; i < 4; ++i) b[i] = (unsigned char)(n >> (i * 8));
}
static uint32_t decode32(const unsigned char b[4]) {
    return (uint32_t)b[0] | (uint32_t)b[1] << 8 | (uint32_t)b[2] << 16 | (uint32_t)b[3] << 24;
}
static int load(Table *table) {
    FILE *file = fopen(DB_FILE, "rb");
    if (!file) return errno == ENOENT ? 0 : -1;
    unsigned char header[8];
    int ok = fread(header, 1, sizeof header, file) == sizeof header &&
             memcmp(header, "GDB1", 4) == 0;
    if (ok) table->count = decode32(header + 4);
    if (!ok || table->count > MAX_ROWS) { fclose(file); return -1; }
    for (uint32_t i = 0; i < table->count; ++i) {
        unsigned char id[4];
        Row *row = &table->rows[i];
        if (fread(id, 1, 4, file) != 4 || fread(row->name, 1, NAME_BYTES, file) != NAME_BYTES ||
            !memchr(row->name, '\0', NAME_BYTES) || row->name[0] == '\0') {
            fclose(file); return -1;
        }
        row->id = decode32(id);
        for (uint32_t j = 0; j < i; ++j)
            if (table->rows[j].id == row->id) { fclose(file); return -1; }
    }
    ok = fgetc(file) == EOF && !ferror(file);
    if (fclose(file) != 0) ok = 0;
    return ok ? 0 : -1;
}
static int save(const Table *table) {
    FILE *file = fopen(DB_FILE ".tmp", "wb");
    if (!file) return -1;
    unsigned char header[8];
    memcpy(header, "GDB1", 4); encode32(header + 4, table->count);
    int ok = fwrite(header, 1, sizeof header, file) == sizeof header;
    for (uint32_t i = 0; ok && i < table->count; ++i) {
        unsigned char id[4]; encode32(id, table->rows[i].id);
        ok = fwrite(id, 1, 4, file) == 4 && fwrite(table->rows[i].name, 1, NAME_BYTES, file) == NAME_BYTES;
    }
    if (fflush(file) != 0 || fsync(fileno(file)) != 0) ok = 0;
    if (fclose(file) != 0) ok = 0;
    if (!ok || rename(DB_FILE ".tmp", DB_FILE) != 0) {
        remove(DB_FILE ".tmp"); return -1;
    }
    return 0;
}
static int parse_id(const char *text, uint32_t *id) {
    if (*text < '0' || *text > '9') return -1;
    errno = 0; char *end;
    unsigned long number = strtoul(text, &end, 10);
    if (errno || *end || number > UINT32_MAX) return -1;
    *id = (uint32_t)number;
    return 0;
}
static void insert(Table *table, uint32_t id, const char *name) {
    for (uint32_t i = 0; i < table->count; ++i)
        if (table->rows[i].id == id) { puts("Error: duplicate id."); return; }
    if (table->count == MAX_ROWS) { puts("Error: table full."); return; }
    Row *row = &table->rows[table->count];
    memset(row, 0, sizeof *row); row->id = id;
    memcpy(row->name, name, strlen(name));
    ++table->count;
    if (save(table) != 0) { --table->count; puts("Error: persistence failed."); }
    else puts("Executed.");
}
static void print_row(const Row *row) {
    printf("(%u, %s)\n", (unsigned)row->id, row->name);
}
static int dispatch(Table *table, const char *line) {
    if (strcmp(line, ".exit") == 0) return 1;
    if (strcmp(line, ".help") == 0) { puts("insert <uint32 id> <name>; select; count; find <uint32 id>; .exit"); return 0; }
    if (strcmp(line, "select") == 0) {
        for (uint32_t i = 0; i < table->count; ++i)
            print_row(&table->rows[i]);
        puts("Executed."); return 0;
    }
    if (strcmp(line, "count") == 0) {
        printf("Count: %u\n", (unsigned)table->count); return 0;
    }
    char command[16], id_text[32], name[NAME_BYTES], extra[2]; uint32_t id;
    int fields = sscanf(line, "%15s %31s %31s %1s", command, id_text, name, extra);
    if (fields == 3 && strcmp(command, "insert") == 0 && parse_id(id_text, &id) == 0)
        insert(table, id, name);
    else if (fields == 2 && strcmp(command, "find") == 0 && parse_id(id_text, &id) == 0) {
        for (uint32_t i = 0; i < table->count; ++i) {
            if (table->rows[i].id == id) {
                print_row(&table->rows[i]);
                return 0;
            }
        }
        puts("Not found.");
    }
    else puts("Error: invalid statement.");
    return 0;
}
int main(void) {
    Table table = {0};
    if (load(&table) != 0) { fputs("Error: invalid database.\n", stderr); return 1; }
    char line[4096];
    while (fgets(line, sizeof line, stdin)) {
        size_t len = strlen(line);
        if (len == sizeof line - 1 && line[len - 1] != '\n') {
            int c; while ((c = getchar()) != '\n' && c != EOF) {}
            puts("Error: input too long."); continue;
        }
        line[strcspn(line, "\r\n")] = '\0';
        if (dispatch(&table, line)) return 0;
    }
    return ferror(stdin) ? 1 : 0;
}
