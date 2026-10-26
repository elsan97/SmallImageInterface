#define SII_BUILD_DLL
#include "sii.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma pack(push, 1)
struct sii_image {
    uint16_t width, height;
    uint8_t  flags;
    uint8_t* pixels;   
};
#pragma pack(pop)

static char g_err[256];

static void set_err(const char* msg) { 
#ifdef _WIN32
    strncpy_s(g_err, sizeof(g_err), msg, _TRUNCATE); 
#else
    strncpy(g_err, msg, sizeof(g_err) - 1);
    g_err[sizeof(g_err) - 1] = '\0';
#endif
}

const char* sii_abi_version(void) { return "1.4.1"; }
const char* sii_last_error(void) { return g_err; }

static uint32_t crc32_calc(const uint8_t* data, size_t len) {
    static uint32_t table[256];
    static int initialized = 0;
    if (!initialized) {
        for (uint32_t i = 0; i < 256; i++) {
            uint32_t c = i;
            for (int k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >> 1)) : (c >> 1);
            table[i] = c;
        }
        initialized = 1;
    }
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < len; i++) crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFF;
}

sii_image* sii_decode(const uint8_t* buf, size_t len) {
    if (!buf || len < sizeof(sii_header_t)) { set_err("Buffer too small"); return NULL; }
    const sii_header_t* h = (const sii_header_t*)buf;
    if (memcmp(h->magic, "SII1", 4) != 0) { set_err("Bad magic"); return NULL; }
    if (h->version != 1) { set_err("Unsupported version"); return NULL; }
    if (h->width > 4096 || h->height > 4096) { set_err("Image too large"); return NULL; }

    sii_image* img = (sii_image*)calloc(1, sizeof(sii_image));
    img->width = h->width; img->height = h->height; img->flags = h->flags;
    img->pixels = (uint8_t*)calloc((size_t)h->width * h->height * 4, 1);

    size_t offset = sizeof(sii_header_t);
    uint32_t* palette = (uint32_t*)malloc(65536 * sizeof(uint32_t));
    uint16_t palette_size = 0;

    for (uint16_t i = 0; i < h->chunk_count; i++) {
        const sii_chunk_t* chunk = (const sii_chunk_t*)(buf + offset);
        offset += sizeof(sii_chunk_t);
        if (offset + chunk->length > len) { sii_free(img); free(palette); return NULL; }

        if (memcmp(chunk->type, "PALT", 4) == 0) {
            palette_size = chunk->length / 4;
            memcpy(palette, buf + offset, chunk->length);
        } else if (memcmp(chunk->type, "DATA", 4) == 0) {
            const uint8_t* ptr = buf + offset;
            const uint8_t* end = ptr + chunk->length;
            size_t pixel_idx = 0;
            size_t max_pixels = (size_t)img->width * img->height;

            while (ptr < end && pixel_idx < max_pixels) {
                if (ptr + 3 > end) break;
                uint8_t index = ptr[0];
                uint16_t run = ptr[1] | (ptr[2] << 8);
                ptr += 3;
                for (uint16_t j = 0; j < run && pixel_idx < max_pixels; j++) {
                    if (index < palette_size) memcpy(&img->pixels[pixel_idx * 4], &palette[index], 4);
                    pixel_idx++;
                }
            }
        }
        offset += chunk->length;
    }
    free(palette);
    return img;
}

sii_image* sii_decode_file(const char* path) {
    FILE* f = NULL;
#ifdef _WIN32
    if (fopen_s(&f, path, "rb") != 0 || !f) return NULL;
#else
    f = fopen(path, "rb");
    if (!f) return NULL;
#endif
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t* buf = (uint8_t*)malloc((size_t)sz);
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { fclose(f); free(buf); return NULL; }
    fclose(f);
    sii_image* img = sii_decode(buf, (size_t)sz);
    free(buf);
    return img;
}

int sii_encode(const sii_image* img, const sii_params* p, uint8_t** out, size_t* out_len) {
    (void)p;
    size_t max_pixels = (size_t)img->width * img->height;
    
    uint32_t palette[256];
    uint16_t palette_size = 0;
    palette[palette_size++] = 0x00000000;

    for (size_t i = 0; i < max_pixels && palette_size < 256; i++) {
        uint8_t a = img->pixels[i*4+3];
        if (a < 128) continue; 
        
        uint32_t color;
        memcpy(&color, &img->pixels[i * 4], 4);
        
        uint8_t r1 = (color >> 0) & 0xFF, g1 = (color >> 8) & 0xFF, b1 = (color >> 16) & 0xFF;
        int is_too_similar = 0;
        
        for (uint16_t j = 0; j < palette_size; j++) {
            uint8_t r2 = (palette[j] >> 0) & 0xFF, g2 = (palette[j] >> 8) & 0xFF, b2 = (palette[j] >> 16) & 0xFF;
            int dist = (r1 - r2)*(r1 - r2) + (g1 - g2)*(g1 - g2) + (b1 - b2)*(b1 - b2);
            if (dist < 1500) { 
                is_too_similar = 1; 
                break; 
            }
        }
        
        if (!is_too_similar) palette[palette_size++] = color;
    }

    size_t max_rle_size = max_pixels * 3;
    uint8_t* rle_buf = (uint8_t*)malloc(max_rle_size);
    size_t rle_len = 0;
    size_t i = 0;

    while (i < max_pixels) {
        uint32_t current_color; memcpy(&current_color, &img->pixels[i * 4], 4);
        uint8_t a1 = (current_color >> 24) & 0xFF;
        
        uint8_t best_index = 0;
        int min_dist = 99999999;

        for (uint16_t j = 0; j < palette_size; j++) {
            uint8_t a2 = (palette[j] >> 24) & 0xFF;
            if (a1 < 128 && a2 == 0) { best_index = (uint8_t)j; break; }
            if (a1 >= 128 && a2 == 0) continue;
            if (a1 < 128 && a2 != 0) continue;

            uint8_t r1 = (current_color >> 0) & 0xFF, g1 = (current_color >> 8) & 0xFF, b1 = (current_color >> 16) & 0xFF;
            uint8_t r2 = (palette[j] >> 0) & 0xFF, g2 = (palette[j] >> 8) & 0xFF, b2 = (palette[j] >> 16) & 0xFF;
            int dist = (r1 - r2)*(r1 - r2) + (g1 - g2)*(g1 - g2) + (b1 - b2)*(b1 - b2);
            if (dist < min_dist) { min_dist = dist; best_index = (uint8_t)j; }
        }

        uint16_t run = 1;
        while (i + run < max_pixels && run < 65535) {
            uint32_t next_color; memcpy(&next_color, &img->pixels[(i + run) * 4], 4);
            uint8_t na1 = (next_color >> 24) & 0xFF;
            uint8_t next_idx = 0;
            int next_min_dist = 99999999;

            for (uint16_t j = 0; j < palette_size; j++) {
                uint8_t na2 = (palette[j] >> 24) & 0xFF;
                if (na1 < 128 && na2 == 0) { next_idx = (uint8_t)j; break; }
                if (na1 >= 128 && na2 == 0) continue;
                if (na1 < 128 && na2 != 0) continue;

                uint8_t nr1 = (next_color >> 0) & 0xFF, ng1 = (next_color >> 8) & 0xFF, nb1 = (next_color >> 16) & 0xFF;
                uint8_t nr2 = (palette[j] >> 0) & 0xFF, ng2 = (palette[j] >> 8) & 0xFF, nb2 = (palette[j] >> 16) & 0xFF;
                int dist = (nr1 - nr2)*(nr1 - nr2) + (ng1 - ng2)*(ng1 - ng2) + (nb1 - nb2)*(nb1 - nb2);
                if (dist < next_min_dist) { next_min_dist = dist; next_idx = (uint8_t)j; }
            }
            if (next_idx != best_index) break;
            run++;
        }

        rle_buf[rle_len + 0] = best_index;
        rle_buf[rle_len + 1] = (uint8_t)(run & 0xFF);
        rle_buf[rle_len + 2] = (uint8_t)((run >> 8) & 0xFF);
        rle_len += 3;
        i += run;
    }

    size_t pal_bytes = palette_size * 4;
    size_t total_size = sizeof(sii_header_t) + (2 * sizeof(sii_chunk_t)) + pal_bytes + rle_len;
    uint8_t* file_buf = (uint8_t*)calloc(1, total_size);

    sii_header_t* h = (sii_header_t*)file_buf;
    memcpy(h->magic, "SII1", 4);
    h->version = 1; h->flags = 1; h->width = img->width; h->height = img->height; h->chunk_count = 2;

    size_t offset = sizeof(sii_header_t);
    sii_chunk_t* chunk1 = (sii_chunk_t*)(file_buf + offset);
    memcpy(chunk1->type, "PALT", 4); chunk1->length = (uint32_t)pal_bytes; chunk1->crc32 = crc32_calc((uint8_t*)palette, pal_bytes);
    offset += sizeof(sii_chunk_t); memcpy(file_buf + offset, palette, pal_bytes); offset += pal_bytes;

    sii_chunk_t* chunk2 = (sii_chunk_t*)(file_buf + offset);
    memcpy(chunk2->type, "DATA", 4); chunk2->length = (uint32_t)rle_len; chunk2->crc32 = crc32_calc(rle_buf, rle_len);
    offset += sizeof(sii_chunk_t); memcpy(file_buf + offset, rle_buf, rle_len);

    free(rle_buf);
    *out = file_buf;
    *out_len = total_size;
    return 0;
}

int sii_encode_file(const sii_image* img, const sii_params* p, const char* path) {
    uint8_t* buf = NULL; size_t len = 0;
    if (sii_encode(img, p, &buf, &len) != 0) return -1;
    FILE* f = NULL;
#ifdef _WIN32
    if (fopen_s(&f, path, "wb") != 0 || !f) return -1;
#else
    f = fopen(path, "wb");
    if (!f) return -1;
#endif
    fwrite(buf, 1, len, f);
    fclose(f); free(buf);
    return 0;
}

void sii_free(sii_image* img) { if (!img) return; free(img->pixels); free(img); }
void sii_free_buf(uint8_t* buf) { free(buf); }


int sii_get_width(const sii_image* img) { return img->width; }
int sii_get_height(const sii_image* img) { return img->height; }
uint8_t* sii_get_pixels(const sii_image* img) { return img->pixels; }