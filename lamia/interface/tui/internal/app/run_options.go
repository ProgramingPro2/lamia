package app

import (
	"encoding/json"
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"lamia/tui/internal/render"
)

type runOption struct {
	Name      string `json:"name"`
	Status    string `json:"status"`
	Target    string `json:"target"`
	Resumable bool   `json:"resumable"`
}

func (m Model) runSummary() string {
	parts := []string{}
	if strings.TrimSpace(m.snapshot.InstructionFile) != "" {
		parts = append(parts, "instructions")
	}
	if n := len(m.snapshot.TargetLists); n > 0 {
		parts = append(parts, fmt.Sprintf("%d target lists", n))
	}
	if n := len(m.snapshot.WorkspaceFiles); n > 0 {
		parts = append(parts, fmt.Sprintf("%d workspace files", n))
	}
	if strings.TrimSpace(m.snapshot.ConfigPath) != "" {
		parts = append(parts, "config")
	}
	mcpSet := strings.TrimSpace(m.snapshot.McpConfig) != "" || len(m.snapshot.McpServers) > 0
	if mcpSet || len(m.snapshot.McpExcluded) > 0 {
		parts = append(parts, "MCP")
	}
	if len(parts) == 0 {
		return "files, MCP, resume"
	}
	return strings.Join(parts, " · ")
}

func (m Model) runRows() []string {
	return []string{"targets", "workspace", "config", "mcp-config", "mcp", "exclude", "resume"}
}

func (m Model) runStep(width int) string {
	switch m.settings.runMode {
	case "mcp":
		return m.mcpPickList(width, false)
	case "exclude":
		return m.mcpPickList(width, true)
	case "resume":
		return m.resumeList(width)
	}
	rows := m.runRows()
	lines := make([]string, 0, len(rows)+1)
	for index, row := range rows {
		label, value := m.runRowText(row)
		lines = append(lines, m.choiceLine(index == m.settings.runCursor, label, value, width))
	}
	if m.settings.modelsError != "" {
		lines = append(lines, truncate(render.Col(amber).Render(m.settings.modelsError), width))
	}
	return strings.Join(lines, "\n")
}

func (m Model) runRowText(row string) (string, string) {
	switch row {
	case "targets":
		return "Target list", joinCount(m.snapshot.TargetLists, "none")
	case "workspace":
		if m.settings.editing == "dest" {
			return "Workspace", m.settings.destInput.View()
		}
		return "Workspace", joinCount(m.snapshot.WorkspaceFiles, "none")
	case "config":
		return "Config", emptyPath(m.snapshot.ConfigPath)
	case "mcp-config":
		return "MCP config", emptyPath(m.snapshot.McpConfig)
	case "mcp":
		if len(m.snapshot.McpServers) == 0 {
			return "MCP servers", "all"
		}
		return "MCP servers", strings.Join(m.snapshot.McpServers, ", ")
	case "exclude":
		if len(m.snapshot.McpExcluded) == 0 {
			return "MCP exclude", "none"
		}
		return "MCP exclude", strings.Join(m.snapshot.McpExcluded, ", ")
	case "resume":
		if len(m.snapshot.Targets) > 0 {
			return "Resume", "not with targets"
		}
		return "Resume", "pick a run"
	default:
		return row, ""
	}
}

func (m Model) runFooter() string {
	switch m.settings.runMode {
	case "mcp", "exclude":
		return "↑/↓ move    space toggle    esc back"
	case "resume":
		return "↑/↓ move    enter resume    esc back"
	default:
		return "↑/↓ row    enter edit    backspace remove    esc back"
	}
}

func (m *Model) moveRun(delta int) {
	switch m.settings.runMode {
	case "mcp", "exclude":
		m.settings.mcpCursor = clampCycle(m.settings.mcpCursor+delta, max(1, len(m.settings.mcpNames)))
	case "resume":
		m.settings.resumeCursor = clampCycle(m.settings.resumeCursor+delta, max(1, len(m.settings.runs)))
	default:
		m.settings.runCursor = clampCycle(m.settings.runCursor+delta, len(m.runRows()))
	}
}

func (m Model) commitRunRow() (tea.Model, tea.Cmd) {
	switch m.settings.runMode {
	case "mcp", "exclude":
		return m.toggleRunSelection()
	case "resume":
		return m.chooseResume()
	}
	rows := m.runRows()
	if m.settings.runCursor >= len(rows) {
		return m, nil
	}
	switch rows[m.settings.runCursor] {
	case "targets":
		return m, m.openFilePicker(pickerTargetList)
	case "workspace":
		return m, m.openFilePicker(pickerWorkspace)
	case "config":
		return m, m.openFilePicker(pickerConfig)
	case "mcp-config":
		return m, m.openFilePicker(pickerMcpConfig)
	case "mcp":
		return m.openNameList("mcp")
	case "exclude":
		return m.openNameList("exclude")
	case "resume":
		if len(m.snapshot.Targets) > 0 {
			m.settings.modelsError = "Resume cannot be combined with targets added on this screen."
			return m, nil
		}
		return m.openResumeList()
	default:
		return m, nil
	}
}

func (m Model) openNameList(mode string) (tea.Model, tea.Cmd) {
	m.settings.runMode = mode
	m.settings.mcpCursor = 0
	m.settings.modelsError = ""
	if m.client == nil {
		return m, nil
	}
	return m, send(m.client, "setup.list_mcp", map[string]any{})
}

func (m Model) openResumeList() (tea.Model, tea.Cmd) {
	m.settings.runMode = "resume"
	m.settings.resumeCursor = 0
	m.settings.modelsError = ""
	if m.client == nil {
		return m, nil
	}
	return m, send(m.client, "setup.list_runs", map[string]any{})
}

func (m Model) removeRunRow() (tea.Model, tea.Cmd) {
	if m.settings.runMode != "" || m.client == nil {
		return m, nil
	}
	rows := m.runRows()
	if m.settings.runCursor >= len(rows) {
		return m, nil
	}
	switch rows[m.settings.runCursor] {
	case "targets":
		if len(m.snapshot.TargetLists) == 0 {
			return m, nil
		}
		last := m.snapshot.TargetLists[len(m.snapshot.TargetLists)-1]
		return m, send(m.client, "setup.remove_target_list", map[string]any{"path": last})
	case "workspace":
		if len(m.snapshot.WorkspaceFiles) == 0 {
			return m, nil
		}
		last := m.snapshot.WorkspaceFiles[len(m.snapshot.WorkspaceFiles)-1]
		return m, send(m.client, "setup.remove_workspace_file", map[string]any{"path": last})
	default:
		return m, nil
	}
}

func (m Model) toggleRunSelection() (tea.Model, tea.Cmd) {
	if m.settings.runMode != "mcp" && m.settings.runMode != "exclude" {
		return m, nil
	}
	if m.client == nil || m.settings.mcpCursor >= len(m.settings.mcpNames) {
		return m, nil
	}
	name := m.settings.mcpNames[m.settings.mcpCursor]
	current := m.snapshot.McpServers
	command := "setup.set_mcp_servers"
	if m.settings.runMode == "exclude" {
		current = m.snapshot.McpExcluded
		command = "setup.set_mcp_exclude"
	}
	next := toggleName(current, name)
	if m.settings.runMode == "exclude" {
		m.snapshot.McpExcluded = next
	} else {
		m.snapshot.McpServers = next
	}
	return m, send(m.client, command, map[string]any{"names": next})
}

func (m Model) chooseResume() (tea.Model, tea.Cmd) {
	if m.client == nil || m.settings.resumeCursor >= len(m.settings.runs) {
		return m, nil
	}
	if len(m.snapshot.Targets) > 0 {
		m.settings.modelsError = "Resume cannot be combined with targets added on this screen."
		return m, nil
	}
	run := m.settings.runs[m.settings.resumeCursor]
	return m, send(m.client, "setup.resume", map[string]any{"run": run.Name})
}

func (m Model) commitWorkspaceDest() (tea.Model, tea.Cmd) {
	path := m.settings.pendingWorkspace
	dest := strings.TrimSpace(m.settings.destInput.Value())
	m.settings.editing = ""
	m.settings.pendingWorkspace = ""
	if path == "" || m.client == nil {
		return m, nil
	}
	payload := map[string]any{"path": path}
	if dest != "" {
		payload["dest"] = dest
	}
	return m, send(m.client, "setup.add_workspace_file", payload)
}

func (m Model) mcpPickList(width int, exclude bool) string {
	names := m.settings.mcpNames
	if len(names) == 0 {
		line := render.Dim().Render("No MCP connections")
		if m.settings.modelsError != "" {
			line += "\n" + truncate(render.Col(amber).Render(m.settings.modelsError), width)
		}
		return line
	}
	selected := m.snapshot.McpServers
	if exclude {
		selected = m.snapshot.McpExcluded
	}
	lines := make([]string, 0, len(names))
	for index, name := range names {
		value := "off"
		if containsName(selected, name) {
			value = "on"
		}
		lines = append(lines, m.choiceLine(index == m.settings.mcpCursor, name, value, width))
	}
	return strings.Join(lines, "\n")
}

func (m Model) resumeList(width int) string {
	if len(m.settings.runs) == 0 {
		return render.Dim().Render("No runs to resume")
	}
	lines := make([]string, 0, len(m.settings.runs))
	for index, run := range m.settings.runs {
		status := run.Status
		if !run.Resumable {
			status = "no agent state"
		}
		lines = append(lines, m.choiceLine(index == m.settings.resumeCursor, run.Name, status, width))
	}
	if len(m.snapshot.Targets) > 0 {
		lines = append(lines, truncate(render.Col(amber).Render("Resume cannot be combined with targets added on this screen."), width))
	}
	return strings.Join(lines, "\n")
}

func (m *Model) applyRunResult(command string, raw json.RawMessage) tea.Cmd {
	m.settings.modelsError = ""
	switch command {
	case "setup.list_mcp", "setup.set_mcp_config":
		var data struct {
			Names []string `json:"names"`
		}
		if err := json.Unmarshal(raw, &data); err != nil {
			m.settings.modelsError = err.Error()
			return nil
		}
		if data.Names == nil {
			data.Names = []string{}
		}
		m.settings.mcpNames = data.Names
	case "setup.list_runs":
		var data struct {
			Runs []runOption `json:"runs"`
		}
		if err := json.Unmarshal(raw, &data); err != nil {
			m.settings.modelsError = err.Error()
			return nil
		}
		if data.Runs == nil {
			data.Runs = []runOption{}
		}
		m.settings.runs = data.Runs
	case "setup.set_config":
		var data struct {
			ScanMode     string   `json:"scan_mode"`
			MaxBudgetUSD *float64 `json:"max_budget_usd"`
			MaxTurns     int      `json:"max_turns"`
			ScopeMode    string   `json:"scope_mode"`
			DiffBase     *string  `json:"diff_base"`
		}
		if err := json.Unmarshal(raw, &data); err != nil {
			m.settings.modelsError = err.Error()
			return nil
		}
		if data.ScanMode != "" {
			m.settings.draft.mode = data.ScanMode
			m.snapshot.ScanMode = data.ScanMode
		}
		if data.ScopeMode != "" {
			m.settings.draft.scope = data.ScopeMode
			m.snapshot.ScopeMode = data.ScopeMode
		}
		if data.MaxTurns > 0 {
			m.settings.draft.turns = fmt.Sprintf("%d", data.MaxTurns)
			m.snapshot.MaxTurns = data.MaxTurns
		}
		m.snapshot.MaxBudgetUSD = data.MaxBudgetUSD
		if data.MaxBudgetUSD == nil {
			m.settings.draft.budget = ""
		} else {
			m.settings.draft.budget = strings.TrimRight(strings.TrimRight(fmt.Sprintf("%f", *data.MaxBudgetUSD), "0"), ".")
		}
		m.snapshot.DiffBase = ""
		m.settings.draft.diffBase = ""
		if data.DiffBase != nil {
			m.snapshot.DiffBase = *data.DiffBase
			m.settings.draft.diffBase = *data.DiffBase
		}
	}
	return nil
}

func joinCount(items []string, empty string) string {
	switch len(items) {
	case 0:
		return empty
	case 1:
		return items[0]
	default:
		return fmt.Sprintf("%d files", len(items))
	}
}

func emptyPath(path string) string {
	if strings.TrimSpace(path) == "" {
		return "none"
	}
	return path
}

func containsName(names []string, want string) bool {
	for _, name := range names {
		if name == want {
			return true
		}
	}
	return false
}

func toggleName(names []string, name string) []string {
	next := make([]string, 0, len(names)+1)
	found := false
	for _, existing := range names {
		if existing == name {
			found = true
			continue
		}
		next = append(next, existing)
	}
	if !found {
		next = append(next, name)
	}
	return next
}
