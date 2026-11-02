// Copyright 2025 OmniSecure Inc.
// Modified by the Lamia project from Strix.

package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"lamia/tui/internal/app"
	"lamia/tui/internal/render"
)

func main() {
	version := os.Getenv("LAMIA_VERSION")
	if version == "" {
		version = os.Getenv("STRIX_VERSION")
	}
	app.SetVersion(version)
	render.DetectKittyGraphics()
	client, err := app.ConnectFromEnvironment()
	if err != nil {
		fmt.Fprintln(os.Stderr, "connect to Lamia backend:", err)
		os.Exit(1)
	}
	defer client.Close()
	if err := client.Handshake(); err != nil {
		fmt.Fprintln(os.Stderr, "negotiate Lamia TUI protocol:", err)
		os.Exit(1)
	}
	program := tea.NewProgram(app.New(client), tea.WithAltScreen(), tea.WithMouseCellMotion())
	finalModel, err := program.Run()
	if err != nil {
		fmt.Fprintln(os.Stderr, "run TUI:", err)
		os.Exit(1)
	}
	if model, ok := finalModel.(interface{ FatalError() error }); ok && model.FatalError() != nil {
		fmt.Fprintln(os.Stderr, "run TUI:", model.FatalError())
		os.Exit(1)
	}
}
