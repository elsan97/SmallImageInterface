package main

import (
	"fmt"
	"image/png"
	"os"
	"path/filepath"
	"strings"
)
func main() {
	if len(os.Args) < 2 {
		fmt.Println("Использование: sii.exe <файл.sii>")
		os.Exit(1)
	}

	inputPath := os.Args[1]
	

	data, err := os.ReadFile(inputPath)
	if err != nil {
		fmt.Printf("Ошибка чтения файла: %v\n", err)
		os.Exit(1)
	}


	img, err := Decode(data)
	if err != nil {
		fmt.Printf("Ошибка декодирования: %v\n", err)
		os.Exit(1)
	}


	outputPath := strings.TrimSuffix(inputPath, filepath.Ext(inputPath)) + "_go.png"


	outFile, err := os.Create(outputPath)
	if err != nil {
		fmt.Printf("Ошибка создания файла: %v\n", err)
		os.Exit(1)
	}
	defer outFile.Close()

	err = png.Encode(outFile, img)
	if err != nil {
		fmt.Printf("Ошибка сохранения PNG: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("✅ Успех! Файл %s декодирован и сохранен как %s\n", inputPath, outputPath)
}