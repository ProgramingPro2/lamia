package app

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/x/ansi"
	"lamia/tui/internal/protocol"
)

func TestStartScreenHintsAtF2Settings(t *testing.T) {
	model := New(nil)
	model.width, model.height = 120, 40
	model.ready = true
	model.showSplash = false
	model.snapshot = protocol.Snapshot{SetupMode: true, Model: "openai/gpt-4o", ScanMode: "deep"}
	view := ansi.Strip(model.viewInner())
	if !strings.Contains(view, "F2 settings") {
		t.Fatalf("model line is missing the F2 hint:\n%s", view)
	}
	if !strings.Contains(view, "f2 settings") {
		t.Fatalf("hint row is missing f2 settings:\n%s", view)
	}

	empty := New(nil)
	empty.width, empty.height = 120, 40
	empty.ready = true
	empty.showSplash = false
	empty.snapshot = protocol.Snapshot{SetupMode: true}
	bare := ansi.Strip(empty.setupSummaryView(80))
	if !strings.Contains(bare, "no model") || !strings.Contains(bare, "F2 to set one up") {
		t.Fatalf("empty model summary = %q", bare)
	}
}

func TestF2OpensSettingsAndEscapeClosesIt(t *testing.T) {
	connection := &recordingConn{}
	model := New(&Client{conn: connection})
	model.width, model.height = 120, 40
	model.ready = true
	model.showSplash = false
	model.snapshot = protocol.Snapshot{SetupMode: true, Model: "openai/gpt-4o", ScanMode: "deep"}

	updated, cmd := model.updateMain(tea.KeyMsg{Type: tea.KeyF2})
	opened := updated.(Model)
	if opened.modal != modalSettings {
		t.Fatal("f2 did not open settings")
	}
	if !strings.Contains(ansi.Strip(opened.modalView()), "Lamia settings") {
		t.Fatalf("settings dialog did not render: %s", opened.modalView())
	}
	types := commandTypes(drainCommands(t, cmd, connection))
	if !contains(types, "setup.list_providers") {
		t.Fatalf("opening settings did not ask for providers: %v", types)
	}

	closed, _ := opened.updateModal(tea.KeyMsg{Type: tea.KeyEsc})
	if closed.(Model).modal != modalNone {
		t.Fatal("esc did not close settings")
	}
}

func TestHelpListsF2(t *testing.T) {
	model := New(nil)
	model.modal = modalHelp
	if !strings.Contains(ansi.Strip(model.modalView()), "F2") || !strings.Contains(ansi.Strip(model.modalView()), "Settings") {
		t.Fatalf("help is missing F2 settings: %s", model.modalView())
	}
}

func TestRunningScanSettingsAreReadOnly(t *testing.T) {
	connection := &recordingConn{}
	model := New(&Client{conn: connection})
	model.width, model.height = 120, 40
	model.ready = true
	model.showSplash = false
	model.snapshot = protocol.Snapshot{
		SetupMode: false, ScanStarted: true, ScanState: "running",
		Model: "openai/gpt-4o", ScanMode: "deep",
	}

	updated, cmd := model.updateMain(tea.KeyMsg{Type: tea.KeyF2})
	opened := updated.(Model)
	if opened.modal != modalSettings || !opened.settings.readOnly {
		t.Fatalf("running scan settings modal=%v readOnly=%v", opened.modal, opened.settings.readOnly)
	}
	view := ansi.Strip(opened.modalView())
	if !strings.Contains(view, "already started") {
		t.Fatalf("read-only notice missing: %s", view)
	}
	types := commandTypes(drainCommands(t, cmd, connection))
	if contains(types, "setup.set_options") || contains(types, "setup.save_connection") || contains(types, "setup.list_providers") {
		t.Fatalf("running scan sent setup commands: %v", types)
	}

	cycled, cmd := opened.updateModal(tea.KeyMsg{Type: tea.KeyRight})
	types = commandTypes(drainCommands(t, cmd, connection))
	if contains(types, "setup.set_options") || contains(types, "setup.save_connection") {
		t.Fatalf("read-only right arrow sent a change: %v", types)
	}
	if cycled.(Model).modal != modalSettings {
		t.Fatal("right arrow closed the read-only dialog")
	}
}

func TestEmptyModelOpensOnboarding(t *testing.T) {
	model := New(nil)
	model.width, model.height = 100, 40
	model.showSplash = false
	model.handleEnvelope(stateEnvelope(t, 1, protocol.Snapshot{SetupMode: true, ScanState: "setup"}))
	if model.modal != modalSettings || model.settings.step != settingsProvider {
		t.Fatalf("onboarding modal=%v step=%d", model.modal, model.settings.step)
	}
}
