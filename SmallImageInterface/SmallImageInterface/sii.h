#ifndef SII_H
#define SII_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifdef SII_BUILD_DLL
#  define SII_API __declspec(dllexport)
#else
#  define SII_API __declspec(dllimport)
#endif

#define SII_ABI_VERSION 1

#define SII_FLAG_HAS_ALPHA   (1u << 0)
#define SII_FLAG_PALETTE     (1u << 1)
#define SII_FLAG_LOSSY       (1u << 2)
#define SII_FLAG_SIGNED      (1u << 3)
#define SII_FLAG_COMPRESSED  (1u << 4)

#pragma pack(push, 1)
    typedef struct {
        char     magic[4];    
        uint8_t  version;
        uint8_t  flags;
        uint16_t width;
        uint16_t height;
        uint16_t chunk_count;
        uint32_t reserved;
    } sii_header_t;           

    typedef struct {
        char     type[4];     
        uint32_t length;
        uint32_t crc32;
    } sii_chunk_t;            
#pragma pack(pop)

    typedef struct sii_image sii_image;

    typedef struct {
        uint32_t lossy_delta_e; 
        int      use_palette;   
        int      use_compress;   
    } sii_params;

    SII_API const char* sii_abi_version(void);
    SII_API const char* sii_last_error(void);

    SII_API sii_image* sii_decode(const uint8_t* buf, size_t len);
    SII_API sii_image* sii_decode_file(const char* path);
    SII_API int         sii_encode(const sii_image* img, const sii_params* p,
        uint8_t** out, size_t* out_len);
    SII_API int         sii_encode_file(const sii_image* img, const sii_params* p,
        const char* path);
    SII_API void        sii_free(sii_image* img);
    SII_API void        sii_free_buf(uint8_t* buf);

#ifdef __cplusplus
}
#endif
#endif