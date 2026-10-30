package app

import (
	"encoding/json"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/x/ansi"
	"lamia/tui/internal/protocol"
)

func TestLaunchScreenOffersInstructionsFile(t *testing.T) {
	model := New(nil)
	model.width, model.height = 120, 40
	model.ready = true
	model.showSplash = false
	model.snapshot = protocol.Snapshot{SetupMode: true, Model: "openai/gpt-4o", ScanMode: "deep"}

	view := ansi.Strip(model.viewInner())
	if !strings.Contains(view, "Instructions") || !strings.Contains(view, "none") {
		t.Fatalf("instructions row missing:\n%s", view)
	}
	if !strings.Contains(view, "f3 instructions") {
		t.Fatalf("hint row is missing f3 instructions:\n%s", view)
	}

	narrow := model
	narrow.width = 36
	narrowView := ansi.Strip(narrow.viewInner())
	if strings.Contains(narrowView, "f3 instructions") {
		t.Fatalf("narrow hint row kept f3:\n%s", narrowView)
	}
	if !strings.Contains(narrowView, ">") {
		t.Fatalf("narrow screen dropped the composer:\n%s", narrowView)
	}
}

func TestF3OpensInstructionsPickerAndEscapeClosesIt(t *testing.T) {
	model := New(nil)
	model.width, model.height = 120, 40
	model.ready = true
	model.showSplash = false
	model.snapshot = protocol.Snapshot{SetupMode: true, WorkingDir: t.TempDir()}

	updated, cmd := model.updateMain(tea.KeyMsg{Type: tea.KeyF3})
	opened := updated.(Model)
	if opened.modal != modalFile {
		t.Fatal("f3 did not open the file picker")
	}
	if cmd == nil {
		t.Fatal("file picker did not start reading its directory")
	}
	view := ansi.Strip(opened.modalView())
	for _, want := range []string{"Instructions", "enter select", "esc close"} {
		if !strings.Contains(view, want) {
			t.Fatalf("picker is missing %q:\n%s", want, view)
		}
	}

	closed, _ := opened.updateModal(tea.KeyMsg{Type: tea.KeyEsc})
	if closed.(Model).modal != modalNone {
		t.Fatal("esc did not close the file picker")
	}
}

func TestClickingInstructionsOpensThePicker(t *testing.T) {
	model := New(nil)
	model.width, model.height = 120, 40
	model.ready = true
	model.showSplash = false
	model.snapshot = protocol.Snapshot{SetupMode: true, WorkingDir: t.TempDir()}

	view := model.setupView()
	clicked := false
	for row, line := range strings.Split(view, "\n") {
		plain := ansi.Strip(line)
		index := strings.Index(plain, "Instructions")
		if index < 0 {
			continue
		}
		updated, _ := model.updateSetupMouse(tea.MouseMsg{
			X: ansi.StringWidth(plain[:index]) + 1, Y: row,
			Button: tea.MouseButtonLeft, Action: tea.MouseActionPress,
		})
		if updated.(Model).modal != modalFile {
			t.Fatal("clicking Instructions did not open the picker")
		}
		clicked = true
		break
	}
	if !clicked {
		t.Fatalf("instructions label was not drawn:\n%s", ansi.Strip(view))
	}
}

func TestFileBackedLaunchKeepsCommandOrder(t *testing.T) {
	connection := &recordingConn{}
	model := New(&Client{conn: connection})
	model.snapshot = protocol.Snapshot{
		SetupMode:       true,
		InstructionFile: "/tmp/playbook.md",
	}

	_, cmd := model.submit("https://app.example.com also check login")
	envelopes := drainCommands(t, cmd, connection)
	types := commandTypes(envelopes)
	for _, want := range []string{"setup.add_target", "setup.set_instruction", "setup.start"} {
		if !contains(types, want) {
			t.Fatalf("missing %s in %v", want, types)
		}
	}
	start := firstIndex(types, "setup.start")
	if target := lastIndex(types, "setup.add_target"); start < target {
		t.Fatalf("setup.start (%d) must come after setup.add_target (%d): %v", start, target, types)
	}
	if instr := lastIndex(types, "setup.set_instruction"); start < instr {
		t.Fatalf("setup.start (%d) must come after setup.set_instruction (%d): %v", start, instr, types)
	}
	var payload struct {
		Instruction string `json:"instruction"`
	}
	for _, envelope := range envelopes {
		if envelope.Type != "setup.set_instruction" {
			continue
		}
		if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
			t.Fatal(err)
		}
	}
	if payload.Instruction != "also check login" {
		t.Fatalf("note = %q, want the non-target text", payload.Instruction)
	}
}

func TestTargetsOnlyPromptLeavesTheInstructionsFile(t *testing.T) {
	connection := &recordingConn{}
	model := New(&Client{conn: connection})
	model.snapshot = protocol.Snapshot{
		SetupMode:       true,
		InstructionFile: "/tmp/playbook.md",
	}

	_, cmd := model.submit("https://app.example.com")
	envelopes := drainCommands(t, cmd, connection)
	var payload struct {
		Instruction string `json:"instruction"`
	}
	found := false
	for _, envelope := range envelopes {
		if envelope.Type != "setup.set_instruction" {
			continue
		}
		found = true
		if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
			t.Fatal(err)
		}
	}
	if !found || payload.Instruction != "" {
		t.Fatalf("targets-only prompt should clear the extra note, got %+v found=%v", payload, found)
	}
}

func TestRunStepListsTheRemainingScanOptions(t *testing.T) {
	model := New(nil)
	model.width, model.height = 120, 40
	model.ready = true
	model.showSplash = false
	model.snapshot = protocol.Snapshot{SetupMode: true, Model: "openai/gpt-4o", ScanMode: "deep"}
	model.openSettings()
	model.settings.step = settingsRun

	view := ansi.Strip(model.settingsView())
	for _, want := range []string{"Target list", "Workspace", "Config", "MCP config", "MCP servers", "MCP exclude", "Resume", "Run"} {
		if !strings.Contains(view, want) {
			t.Fatalf("run step is missing %q:\n%s", want, view)
		}
	}
}
