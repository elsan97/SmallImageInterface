package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"hash/crc32"
	"image"
	"image/color"
)

const magic = "SII1"

type Header struct {
	Magic      [4]byte
	Version    uint8
	Flags      uint8
	Width      uint16
	Height     uint16
	ChunkCount uint16
	Reserved   uint32
}

type Chunk struct {
	Type   [4]byte
	Length uint32
	CRC32  uint32
}

func Decode(data []byte) (image.Image, error) {
	if len(data) < 16 {
		return nil, fmt.Errorf("файл слишком маленький")
	}

	var h Header
	err := binary.Read(bytes.NewReader(data), binary.LittleEndian, &h)
	if err != nil {
		return nil, err
	}

	if string(h.Magic[:]) != magic {
		return nil, fmt.Errorf("неверная магия файла: %s", string(h.Magic[:]))
	}

	if h.Width > 4096 || h.Height > 4096 {
		return nil, fmt.Errorf("картинка слишком большая: %dx%d", h.Width, h.Height)
	}

	img := image.NewRGBA(image.Rect(0, 0, int(h.Width), int(h.Height)))
	offset := 16
	var palette []color.RGBA

	for i := 0; i < int(h.ChunkCount); i++ {
		if offset+12 > len(data) {
			return nil, fmt.Errorf("неожиданный конец файла (заголовок чанка)")
		}

		var c Chunk
		binary.Read(bytes.NewReader(data[offset:]), binary.LittleEndian, &c)
		offset += 12

		if offset+int(c.Length) > len(data) {
			return nil, fmt.Errorf("неожиданный конец файла (данные чанка)")
		}

		chunkData := data[offset : offset+int(c.Length)]
		
		calcCRC := crc32.ChecksumIEEE(chunkData)
		if calcCRC != c.CRC32 {
			return nil, fmt.Errorf("CRC32 не совпадает! Файл поврежден")
		}

		chunkType := string(c.Type[:])
		
		switch chunkType {
		case "PALT":
			numColors := len(chunkData) / 4
			palette = make([]color.RGBA, numColors)
			for j := 0; j < numColors; j++ {
				palette[j] = color.RGBA{
					R: chunkData[j*4+0],
					G: chunkData[j*4+1],
					B: chunkData[j*4+2],
					A: chunkData[j*4+3],
				}
			}

		case "DATA":
			if len(palette) == 0 {
				return nil, fmt.Errorf("найден чанк DATA до чанка PALT")
			}

			ptr := 0
			pixelIdx := 0
			maxPixels := int(h.Width) * int(h.Height)

			for ptr < len(chunkData) && pixelIdx < maxPixels {
				if ptr+3 > len(chunkData) {
					return nil, fmt.Errorf("битый чанк DATA")
				}
				
				index := chunkData[ptr]
				run := binary.LittleEndian.Uint16(chunkData[ptr+1 : ptr+3])
				ptr += 3

				if int(index) >= len(palette) {
					return nil, fmt.Errorf("индекс цвета вне палитры")
				}

				col := palette[index]
				for j := 0; j < int(run) && pixelIdx < maxPixels; j++ {
					img.SetRGBA(pixelIdx%int(h.Width), pixelIdx/int(h.Width), col)
					pixelIdx++
				}
			}
		}

		offset += int(c.Length)
	}

	return img, nil
}