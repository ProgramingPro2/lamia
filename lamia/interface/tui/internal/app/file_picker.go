package app

import (
	"os"
	"strings"

	"github.com/charmbracelet/bubbles/filepicker"
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"lamia/tui/internal/render"
)

type pickerPurpose int

const (
	pickerInstruction pickerPurpose = iota
	pickerTargetList
	pickerWorkspace
	pickerConfig
	pickerMcpConfig
)

type filePickerState struct {
	purpose  pickerPurpose
	returnTo modalMode
	files    filepicker.Model
	path     textinput.Model
	editing  bool
}

func (m *Model) openInstructionPicker() (tea.Model, tea.Cmd) {
	cmd := m.openFilePicker(pickerInstruction)
	return *m, cmd
}

func (m *Model) openFilePicker(purpose pickerPurpose) tea.Cmd {
	m.picker.purpose = purpose
	m.picker.returnTo = modalNone
	if m.modal == modalSettings {
		m.picker.returnTo = modalSettings
	}
	m.picker.editing = false
	dir := strings.TrimSpace(m.snapshot.WorkingDir)
	if dir == "" {
		if wd, err := os.Getwd(); err == nil {
			dir = wd
		} else {
			dir = "."
		}
	}
	files := filepicker.New()
	files.CurrentDirectory = dir
	files.AutoHeight = false
	files.ShowPermissions = false
	files.ShowSize = false
	files.ShowHidden = false
	files.FileAllowed = true
	files.DirAllowed = false
	files.Cursor = "▸"
	height := 8
	if m.height > 16 {
		height = min(12, m.height-14)
	}
	files.SetHeight(max(4, height))
	files.Styles = filePickerStyles()
	files.KeyMap.Back = key.NewBinding(key.WithKeys("backspace", "left", "h"))
	m.picker.files = files
	m.picker.path = newPlainInput("/path/to/file")
	m.openModal(modalFile)
	return files.Init()
}

func (m *Model) closeFilePicker() {
	back := m.picker.returnTo
	m.picker.editing = false
	m.picker.returnTo = modalNone
	if back == modalSettings {
		m.modal = modalSettings
		return
	}
	m.closeModal()
}

func (m Model) updateFilePicker(key tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.picker.editing {
		switch key.String() {
		case "esc":
			m.picker.editing = false
			return m, nil
		case "enter":
			path := strings.TrimSpace(m.picker.path.Value())
			m.picker.editing = false
			if path == "" {
				return m, nil
			}
			return m, m.choosePickedPath(path)
		}
		var cmd tea.Cmd
		m.picker.path, cmd = m.picker.path.Update(key)
		return m, cmd
	}
	switch key.String() {
	case "esc":
		m.closeFilePicker()
		return m, nil
	case "c":
		if m.picker.purpose == pickerInstruction && strings.TrimSpace(m.snapshot.InstructionFile) != "" {
			m.closeFilePicker()
			if m.client == nil {
				return m, nil
			}
			return m, send(m.client, "setup.set_instruction_file", map[string]any{"path": ""})
		}
	case "/":
		m.picker.editing = true
		m.picker.path.Focus()
		return m, nil
	}
	var cmd tea.Cmd
	m.picker.files, cmd = m.picker.files.Update(key)
	if selected, path := m.picker.files.DidSelectFile(key); selected && path != "" {
		return m, tea.Batch(cmd, m.choosePickedPath(path))
	}
	return m, cmd
}

func (m *Model) choosePickedPath(path string) tea.Cmd {
	purpose := m.picker.purpose
	m.closeFilePicker()
	if m.client == nil && purpose != pickerWorkspace {
		return nil
	}
	switch purpose {
	case pickerInstruction:
		return send(m.client, "setup.set_instruction_file", map[string]any{"path": path})
	case pickerTargetList:
		return send(m.client, "setup.add_target_list", map[string]any{"path": path})
	case pickerWorkspace:
		m.settings.ensureInputs()
		m.settings.pendingWorkspace = path
		m.settings.destInput.SetValue("")
		m.settings.destInput.Focus()
		m.settings.editing = "dest"
		return nil
	case pickerConfig:
		return send(m.client, "setup.set_config", map[string]any{"path": path})
	case pickerMcpConfig:
		return send(m.client, "setup.set_mcp_config", map[string]any{"path": path})
	default:
		return nil
	}
}

func (m Model) filePickerView() string {
	width := min(76, max(36, m.width))
	if m.width > 0 && width > m.width {
		width = m.width
	}
	inner := max(12, width-6)
	title := lipgloss.NewStyle().Bold(true).Foreground(green).Width(inner).Align(lipgloss.Center).Render(m.pickerTitle())
	directory := truncate(render.Dim().Render(truncatePath(m.picker.files.CurrentDirectory, inner)), inner)
	body := directory + "\n\n" + strings.TrimRight(m.picker.files.View(), "\n")
	pathValue := "type a path with /"
	if m.picker.editing || strings.TrimSpace(m.picker.path.Value()) != "" {
		pathValue = m.picker.path.View()
	}
	body += "\n\n" + m.fieldLine("Path", pathValue, m.picker.editing, inner)
	body += "\n\n" + render.Dim().Render(m.pickerFooter())
	content := title + "\n\n" + body
	return lipgloss.NewStyle().Width(max(12, width-2)).Border(lipgloss.RoundedBorder()).BorderForeground(green).Background(black).Padding(1, 2).Render(content)
}

func (m Model) pickerTitle() string {
	switch m.picker.purpose {
	case pickerTargetList:
		return "Target list"
	case pickerWorkspace:
		return "Workspace file"
	case pickerConfig:
		return "Config"
	case pickerMcpConfig:
		return "MCP config"
	default:
		return "Instructions"
	}
}

func (m Model) pickerFooter() string {
	footer := "enter select    / path    esc close"
	if m.picker.purpose == pickerInstruction && strings.TrimSpace(m.snapshot.InstructionFile) != "" {
		footer += "    c clear"
	}
	return footer
}

func filePickerStyles() filepicker.Styles {
	styles := filepicker.DefaultStyles()
	styles.Cursor = lipgloss.NewStyle().Foreground(green)
	styles.Selected = lipgloss.NewStyle().Foreground(white).Bold(true)
	styles.Directory = lipgloss.NewStyle().Foreground(dim)
	styles.File = lipgloss.NewStyle().Foreground(textColor)
	styles.DisabledFile = render.Dim()
	styles.DisabledSelected = render.Dim()
	styles.EmptyDirectory = lipgloss.NewStyle().Foreground(dim).SetString("Empty directory")
	return styles
}
