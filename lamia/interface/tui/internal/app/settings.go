package app

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"lamia/tui/internal/render"
)

const (
	settingsSummary = iota
	settingsProvider
	settingsKey
	settingsModel
	settingsScan
)

type settingsPollMsg struct{}

type providerOption struct {
	ID        string `json:"id"`
	Label     string `json:"label"`
	NeedsKey  bool   `json:"needs_key"`
	NeedsBase bool   `json:"needs_base"`
}

type modelOption struct {
	ID    string `json:"id"`
	Tools *bool  `json:"tools"`
}

type modelInfo struct {
	ID                string   `json:"id"`
	MaxInput          int      `json:"max_input_tokens"`
	MaxOutput         int      `json:"max_output_tokens"`
	InputCost         *float64 `json:"input_cost_per_million"`
	OutputCost        *float64 `json:"output_cost_per_million"`
	SupportsTools     *bool    `json:"supports_tools"`
	SupportsReasoning bool     `json:"supports_reasoning"`
	ReasoningLevels   []string `json:"reasoning_levels"`
}

type scanDraft struct {
	mode          string
	budget        string
	turns         string
	scope         string
	diffBase      string
	reasoning     string
	levels        []string
	showReasoning bool
}

type settingsState struct {
	step           int
	fromSummary    bool
	readOnly       bool
	summaryCursor  int
	providers      []providerOption
	providerCursor int
	providerFilter string
	providerID     string
	models         []modelOption
	modelCursor    int
	modelFilter    string
	modelSource    string
	modelNote      string
	modelsLoading  bool
	modelsError    string
	details        modelInfo
	draft          scanDraft
	editing        string
	keyCursor      int
	keyInput       textinput.Model
	baseInput      textinput.Model
	budgetInput    textinput.Model
	turnsInput     textinput.Model
	diffInput      textinput.Model
	manualInput    textinput.Model
	pasteInput     textinput.Model
	inputsReady    bool
	authURL        string
	authWaiting    bool
	authError      string
	scanCursor     int
}

func scheduleSettingsPoll() tea.Cmd {
	return tea.Tick(400*time.Millisecond, func(time.Time) tea.Msg { return settingsPollMsg{} })
}

func (m *Model) openSettings() tea.Cmd {
	m.settings.ensureInputs()
	m.settings.readOnly = !m.snapshot.SetupMode || m.snapshot.ScanStarted
	m.settings.fromSummary = strings.TrimSpace(m.snapshot.Model) != ""
	m.settings.editing = ""
	m.settings.providerFilter = ""
	m.settings.modelFilter = ""
	m.settings.authWaiting = false
	m.settings.authError = ""
	m.settings.modelsError = ""
	if m.settings.providerID == "" {
		m.settings.providerID = providerIDFromModel(m.snapshot.Model)
	}
	m.loadScanDraft()
	if m.settings.fromSummary || m.settings.readOnly {
		m.settings.step = settingsSummary
	} else {
		m.settings.step = settingsProvider
	}
	m.openModal(modalSettings)
	if m.settings.readOnly || m.client == nil {
		return nil
	}
	return send(m.client, "setup.list_providers", map[string]any{})
}

func (m *Model) loadScanDraft() {
	budget := ""
	if m.snapshot.MaxBudgetUSD != nil {
		budget = strconv.FormatFloat(*m.snapshot.MaxBudgetUSD, 'f', -1, 64)
	}
	turns := m.snapshot.MaxTurns
	if turns <= 0 {
		turns = 500
	}
	mode := m.snapshot.ScanMode
	if mode == "" {
		mode = "deep"
	}
	scope := m.snapshot.ScopeMode
	if scope == "" {
		scope = "auto"
	}
	reasoning := m.snapshot.ReasoningEffort
	if reasoning == "" {
		reasoning = "high"
	}
	levels := m.snapshot.ReasoningLevels
	if len(levels) == 0 {
		levels = []string{"none", "minimal", "low", "medium", "high", "xhigh", "max"}
	}
	m.settings.draft = scanDraft{
		mode: mode, budget: budget, turns: strconv.Itoa(turns), scope: scope,
		diffBase: m.snapshot.DiffBase, reasoning: reasoning, levels: levels,
		showReasoning: m.snapshot.SupportsReasoning,
	}
	m.settings.scanCursor = 0
}

func (m *Model) dismissSettings() tea.Cmd {
	waiting := m.settings.authWaiting
	m.settings.authWaiting = false
	m.settings.editing = ""
	m.closeModal()
	if waiting && m.client != nil && m.snapshot.SetupMode && !m.snapshot.ScanStarted {
		return send(m.client, "setup.cancel_auth", map[string]any{})
	}
	return nil
}

func (s *settingsState) ensureInputs() {
	if s.inputsReady {
		return
	}
	s.keyInput = newSecretInput()
	s.baseInput = newPlainInput("https://host/v1")
	s.budgetInput = newPlainInput("no cap")
	s.turnsInput = newPlainInput("500")
	s.diffInput = newPlainInput("default branch")
	s.manualInput = newPlainInput("provider/model")
	s.pasteInput = newPlainInput("paste the redirect URL")
	s.inputsReady = true
}

func newPlainInput(placeholder string) textinput.Model {
	input := textinput.New()
	input.Prompt = ""
	input.Placeholder = placeholder
	input.CharLimit = 512
	input.Width = 42
	input.Cursor.Style = lipgloss.NewStyle().Foreground(green)
	return input
}

func newSecretInput() textinput.Model {
	input := newPlainInput("API key")
	input.EchoMode = textinput.EchoPassword
	input.EchoCharacter = '•'
	return input
}

func (m Model) updateSettings(key tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.settings.readOnly {
		if key.String() == "esc" || key.String() == "enter" || key.String() == "q" {
			m.closeModal()
		}
		return m, nil
	}
	if m.settings.editing != "" {
		return m.updateSettingsEdit(key)
	}
	switch key.String() {
	case "esc":
		return m.backSettings()
	case "up":
		m.moveSettings(-1)
		return m, m.detailsForCursor()
	case "down":
		m.moveSettings(1)
		return m, m.detailsForCursor()
	case "left":
		return m.cycleSettings(-1)
	case "right":
		return m.cycleSettings(1)
	case "enter":
		return m.commitSettings()
	case "backspace":
		m.trimSettingsFilter()
		return m, m.detailsForCursor()
	default:
		if m.appendSettingsFilter(key.String()) {
			return m, m.detailsForCursor()
		}
	}
	return m, nil
}

func (m Model) updateSettingsEdit(key tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch key.String() {
	case "esc":
		m.settings.editing = ""
		return m, nil
	case "enter":
		field := m.settings.editing
		m.settings.editing = ""
		if field == "paste" {
			redirect := strings.TrimSpace(m.settings.pasteInput.Value())
			if redirect == "" || m.client == nil {
				return m, nil
			}
			return m, send(m.client, "setup.complete_auth", map[string]any{"redirect": redirect})
		}
		if field == "key" || field == "base" {
			return m.continueFromKey()
		}
		if field == "manual" {
			id := strings.TrimSpace(m.settings.manualInput.Value())
			if id == "" {
				return m, nil
			}
			return m, m.saveModel(id)
		}
		if !m.commitDraftField(field) {
			m.settings.editing = field
			return m, nil
		}
		return m, m.sendScanOptions()
	}
	var cmd tea.Cmd
	switch m.settings.editing {
	case "key":
		m.settings.keyInput, cmd = m.settings.keyInput.Update(key)
	case "base":
		m.settings.baseInput, cmd = m.settings.baseInput.Update(key)
	case "budget":
		m.settings.budgetInput, cmd = m.settings.budgetInput.Update(key)
	case "turns":
		m.settings.turnsInput, cmd = m.settings.turnsInput.Update(key)
	case "diff":
		m.settings.diffInput, cmd = m.settings.diffInput.Update(key)
	case "manual":
		m.settings.manualInput, cmd = m.settings.manualInput.Update(key)
	case "paste":
		m.settings.pasteInput, cmd = m.settings.pasteInput.Update(key)
	}
	return m, cmd
}

func (m Model) backSettings() (tea.Model, tea.Cmd) {
	if m.settings.fromSummary && m.settings.step != settingsSummary {
		m.settings.step = settingsSummary
		m.settings.editing = ""
		return m, nil
	}
	switch m.settings.step {
	case settingsKey:
		m.settings.step = settingsProvider
		return m, m.dismissAuthOnly()
	case settingsModel:
		m.settings.step = settingsKey
		return m, nil
	case settingsScan:
		m.settings.step = settingsModel
		return m, nil
	default:
		return m, m.dismissSettings()
	}
}

func (m *Model) focusChatGPTPaste() {
	m.settings.editing = "paste"
	m.settings.pasteInput.Focus()
}

func (m *Model) dismissAuthOnly() tea.Cmd {
	if !m.settings.authWaiting || m.client == nil {
		m.settings.authWaiting = false
		return nil
	}
	m.settings.authWaiting = false
	return send(m.client, "setup.cancel_auth", map[string]any{})
}

func (m *Model) moveSettings(delta int) {
	switch m.settings.step {
	case settingsSummary:
		m.settings.summaryCursor = clampCycle(m.settings.summaryCursor+delta, len(m.summaryRows()))
	case settingsProvider:
		m.settings.providerCursor = clampCycle(m.settings.providerCursor+delta, max(1, len(m.filteredProviders())))
	case settingsKey:
		choices := 1
		if m.providerNeedsBase() {
			choices = 2
		}
		m.settings.keyCursor = clampCycle(m.settings.keyCursor+delta, choices)
	case settingsModel:
		m.settings.modelCursor = clampCycle(m.settings.modelCursor+delta, max(1, m.modelChoiceCount()))
	case settingsScan:
		m.settings.scanCursor = clampCycle(m.settings.scanCursor+delta, len(m.scanRows()))
	}
}

func (m Model) commitSettings() (tea.Model, tea.Cmd) {
	switch m.settings.step {
	case settingsSummary:
		rows := m.summaryRows()
		if len(rows) == 0 {
			return m, nil
		}
		m.settings.step = rows[m.settings.summaryCursor].step
		m.settings.fromSummary = true
		return m, nil
	case settingsProvider:
		list := m.filteredProviders()
		if len(list) == 0 {
			return m, nil
		}
		chosen := list[min(m.settings.providerCursor, len(list)-1)]
		m.settings.providerID = chosen.ID
		if chosen.ID == "chatgpt" && m.snapshot.ChatGPTSignedIn {
			m.settings.step = settingsModel
			return m, m.requestModels()
		}
		if chosen.ID == "chatgpt" {
			m.settings.step = settingsKey
			m.focusChatGPTPaste()
			if m.client == nil {
				return m, nil
			}
			return m, send(m.client, "setup.begin_auth", map[string]any{})
		}
		m.settings.step = settingsKey
		if chosen.NeedsBase && strings.TrimSpace(m.settings.baseInput.Value()) == "" && chosen.ID == "ollama" {
			m.settings.baseInput.SetValue("http://localhost:11434")
		}
		return m, nil
	case settingsKey:
		return m.editKeyRow()
	case settingsModel:
		if m.settings.modelCursor >= len(m.filteredModels()) {
			m.settings.editing = "manual"
			m.settings.manualInput.Focus()
			return m, nil
		}
		list := m.filteredModels()
		if len(list) == 0 {
			return m, nil
		}
		return m, m.saveModel(list[m.settings.modelCursor].ID)
	case settingsScan:
		return m.editScanRow()
	}
	return m, nil
}

func (m Model) editKeyRow() (tea.Model, tea.Cmd) {
	if m.settings.providerID == "chatgpt" {
		if m.snapshot.ChatGPTSignedIn {
			return m.continueFromKey()
		}
		m.focusChatGPTPaste()
		return m, nil
	}
	if m.settings.keyCursor == 1 && m.providerNeedsBase() {
		m.settings.editing = "base"
		m.settings.baseInput.Focus()
		return m, nil
	}
	if m.providerNeedsKey() {
		m.settings.editing = "key"
		m.settings.keyInput.Focus()
		return m, nil
	}
	return m.continueFromKey()
}

func (m Model) continueFromKey() (tea.Model, tea.Cmd) {
	m.settings.step = settingsModel
	return m, m.requestModels()
}

func (m Model) editScanRow() (tea.Model, tea.Cmd) {
	rows := m.scanRows()
	if m.settings.scanCursor >= len(rows) {
		return m, nil
	}
	switch rows[m.settings.scanCursor] {
	case "budget":
		m.settings.editing = "budget"
		m.settings.budgetInput.SetValue(m.settings.draft.budget)
		m.settings.budgetInput.Focus()
	case "turns":
		m.settings.editing = "turns"
		m.settings.turnsInput.SetValue(m.settings.draft.turns)
		m.settings.turnsInput.Focus()
	case "diff":
		m.settings.editing = "diff"
		m.settings.diffInput.SetValue(m.settings.draft.diffBase)
		m.settings.diffInput.Focus()
	default:
		return m.cycleSettings(1)
	}
	return m, nil
}

func (m Model) cycleSettings(delta int) (tea.Model, tea.Cmd) {
	if m.settings.step != settingsScan {
		return m, nil
	}
	rows := m.scanRows()
	if m.settings.scanCursor >= len(rows) {
		return m, nil
	}
	switch rows[m.settings.scanCursor] {
	case "mode":
		m.settings.draft.mode = cycleString(scanModeOrder, m.settings.draft.mode, delta)
	case "scope":
		m.settings.draft.scope = cycleString([]string{"auto", "diff", "full"}, m.settings.draft.scope, delta)
	case "reasoning":
		levels := m.settings.draft.levels
		if len(levels) == 0 {
			levels = []string{"none", "minimal", "low", "medium", "high", "xhigh", "max"}
		}
		m.settings.draft.reasoning = cycleString(levels, m.settings.draft.reasoning, delta)
	default:
		return m, nil
	}
	return m, m.sendScanOptions()
}

func (m *Model) commitDraftField(field string) bool {
	switch field {
	case "budget":
		value := strings.TrimSpace(m.settings.budgetInput.Value())
		if value != "" {
			amount, err := strconv.ParseFloat(value, 64)
			if err != nil || amount <= 0 {
				m.settings.modelsError = "Budget must be a number greater than 0, or empty for no cap"
				return false
			}
		}
		m.settings.draft.budget = value
		m.settings.modelsError = ""
	case "turns":
		turns, err := strconv.Atoi(strings.TrimSpace(m.settings.turnsInput.Value()))
		if err != nil || turns <= 0 {
			m.settings.modelsError = "Turns must be an integer greater than 0"
			return false
		}
		m.settings.draft.turns = strconv.Itoa(turns)
		m.settings.modelsError = ""
	case "diff":
		m.settings.draft.diffBase = strings.TrimSpace(m.settings.diffInput.Value())
	}
	return true
}

func (m Model) sendScanOptions() tea.Cmd {
	if m.settings.readOnly || m.client == nil || !m.snapshot.SetupMode || m.snapshot.ScanStarted {
		return nil
	}
	payload := map[string]any{
		"scan_mode":  m.settings.draft.mode,
		"max_turns":  m.settings.draft.turns,
		"scope_mode": m.settings.draft.scope,
		"diff_base":  m.settings.draft.diffBase,
	}
	if strings.TrimSpace(m.settings.draft.budget) == "" {
		payload["max_budget_usd"] = nil
	} else {
		payload["max_budget_usd"] = m.settings.draft.budget
	}
	if m.settings.draft.showReasoning || m.snapshot.SupportsReasoning {
		payload["reasoning_effort"] = m.settings.draft.reasoning
	}
	return send(m.client, "setup.set_options", payload)
}

func (m *Model) requestModels() tea.Cmd {
	m.settings.modelsLoading = true
	m.settings.modelsError = ""
	m.settings.modelNote = ""
	m.settings.models = nil
	m.settings.step = settingsModel
	if m.client == nil {
		m.settings.modelsLoading = false
		return nil
	}
	payload := map[string]any{"provider": m.settings.providerID}
	if key := strings.TrimSpace(m.settings.keyInput.Value()); key != "" {
		payload["api_key"] = key
	}
	if m.providerNeedsBase() {
		payload["api_base"] = strings.TrimSpace(m.settings.baseInput.Value())
	}
	return send(m.client, "setup.list_models", payload)
}

func (m *Model) saveModel(id string) tea.Cmd {
	m.settings.step = settingsScan
	m.settings.editing = ""
	if m.client == nil || m.settings.readOnly {
		return nil
	}
	payload := map[string]any{"model": id}
	if key := strings.TrimSpace(m.settings.keyInput.Value()); key != "" {
		payload["api_key"] = key
	}
	if m.providerNeedsBase() {
		payload["api_base"] = strings.TrimSpace(m.settings.baseInput.Value())
	}
	return tea.Batch(send(m.client, "setup.save_connection", payload), m.requestDetails(id))
}

func (m *Model) requestDetails(id string) tea.Cmd {
	if m.client == nil || id == "" {
		return nil
	}
	return send(m.client, "setup.model_info", map[string]any{"model": id})
}

func (m *Model) detailsForCursor() tea.Cmd {
	if m.settings.step != settingsModel {
		return nil
	}
	list := m.filteredModels()
	if m.settings.modelCursor < 0 || m.settings.modelCursor >= len(list) {
		return nil
	}
	return m.requestDetails(list[m.settings.modelCursor].ID)
}

func (m *Model) applySettingsResult(command string, raw json.RawMessage) tea.Cmd {
	switch command {
	case "setup.list_providers":
		var data struct {
			Providers []providerOption `json:"providers"`
		}
		if err := json.Unmarshal(raw, &data); err != nil {
			m.settings.modelsError = err.Error()
			return nil
		}
		m.settings.providers = data.Providers
		return nil
	case "setup.list_models":
		var data struct {
			Source    string        `json:"source"`
			Note      string        `json:"note"`
			Models    []modelOption `json:"models"`
			Truncated bool          `json:"truncated"`
		}
		m.settings.modelsLoading = false
		if err := json.Unmarshal(raw, &data); err != nil {
			m.settings.modelsError = err.Error()
			return nil
		}
		m.settings.models = data.Models
		m.settings.modelSource = data.Source
		m.settings.modelNote = data.Note
		if data.Truncated {
			m.settings.modelNote = strings.TrimSpace(m.settings.modelNote + " List truncated. Type to narrow it.")
		}
		m.settings.modelCursor = defaultModelCursor(m.filteredModels())
		list := m.filteredModels()
		if m.settings.modelCursor < len(list) {
			return m.requestDetails(list[m.settings.modelCursor].ID)
		}
		return nil
	case "setup.model_info":
		var info modelInfo
		if err := json.Unmarshal(raw, &info); err != nil {
			return nil
		}
		m.settings.details = info
		if info.SupportsReasoning {
			m.settings.draft.showReasoning = true
			if len(info.ReasoningLevels) > 0 {
				m.settings.draft.levels = info.ReasoningLevels
			}
		}
		return nil
	case "setup.begin_auth":
		var data struct {
			AuthorizeURL string `json:"authorize_url"`
			Waiting      bool   `json:"waiting"`
		}
		if err := json.Unmarshal(raw, &data); err != nil {
			m.settings.authError = err.Error()
			return nil
		}
		m.settings.authURL = data.AuthorizeURL
		m.settings.authWaiting = data.Waiting
		m.settings.step = settingsKey
		m.settings.providerID = "chatgpt"
		if data.Waiting {
			return scheduleSettingsPoll()
		}
		return nil
	case "setup.poll_auth", "setup.complete_auth":
		var data struct {
			Status  string `json:"status"`
			Message string `json:"message"`
		}
		if err := json.Unmarshal(raw, &data); err != nil {
			m.settings.authError = err.Error()
			m.settings.authWaiting = false
			return nil
		}
		if data.Status == "authenticated" {
			m.settings.authWaiting = false
			m.settings.authError = ""
			m.settings.editing = ""
			m.snapshot.ChatGPTSignedIn = true
			return m.requestModels()
		}
		if data.Status == "error" {
			m.settings.authWaiting = false
			m.settings.authError = data.Message
			return nil
		}
		if m.settings.authWaiting {
			return scheduleSettingsPoll()
		}
		return nil
	default:
		return nil
	}
}

func (m Model) settingsView() string {
	width := min(76, max(36, m.width))
	if m.width > 0 && width > m.width {
		width = m.width
	}
	innerWidth := max(12, width-6)
	title := lipgloss.NewStyle().Bold(true).Foreground(green).Width(innerWidth).Align(lipgloss.Center).Render("Lamia settings")
	var body string
	if m.settings.readOnly {
		body = render.Col(amber).Render("This scan already started with these settings.")
	} else {
		body = m.settingsSteps(innerWidth)
	}
	body += "\n\n" + m.settingsStepBody(innerWidth)
	if footer := m.settingsFooter(); footer != "" {
		body += "\n\n" + render.Dim().Render(footer)
	}
	content := title + "\n\n" + body
	return lipgloss.NewStyle().Width(max(12, width-2)).Border(lipgloss.RoundedBorder()).BorderForeground(green).Background(black).Padding(1, 2).Render(content)
}

func (m Model) settingsSteps(width int) string {
	labels := []struct {
		step  int
		label string
	}{
		{settingsProvider, "Provider"},
		{settingsKey, "Key"},
		{settingsModel, "Model"},
		{settingsScan, "Scan"},
	}
	parts := make([]string, 0, len(labels))
	for _, item := range labels {
		if item.step == m.settings.step {
			parts = append(parts, render.Col(white).Render(item.label))
			continue
		}
		parts = append(parts, render.Dim().Render(item.label))
	}
	return truncate(strings.Join(parts, render.Dim().Render("  ")), width)
}

func (m Model) settingsStepBody(width int) string {
	switch m.settings.step {
	case settingsProvider:
		return m.providerStep(width)
	case settingsKey:
		return m.keyStep(width)
	case settingsModel:
		return m.modelStep(width)
	case settingsScan:
		return m.scanStep(width)
	default:
		return m.summaryStep(width)
	}
}

type summaryRow struct {
	step  int
	label string
	value string
}

func (m Model) summaryRows() []summaryRow {
	key := "not set"
	if m.snapshot.ChatGPTSignedIn && strings.HasPrefix(m.snapshot.Model, "chatgpt/") {
		key = "ChatGPT subscription"
	} else if m.snapshot.KeyConfigured {
		key = m.snapshot.KeyHint
		if key == "" {
			key = "saved"
		}
	}
	model := strings.TrimSpace(m.snapshot.Model)
	if model == "" {
		model = "not set"
	}
	budget := "no cap"
	if m.snapshot.MaxBudgetUSD != nil {
		budget = fmt.Sprintf("$%.2f", *m.snapshot.MaxBudgetUSD)
	}
	mode := m.snapshot.ScanMode
	if mode == "" {
		mode = "deep"
	}
	turns := m.snapshot.MaxTurns
	if turns <= 0 {
		turns = 500
	}
	scope := m.snapshot.ScopeMode
	if scope == "" {
		scope = "auto"
	}
	return []summaryRow{
		{settingsProvider, "Provider", providerLabelFromModel(m.snapshot.Model)},
		{settingsKey, "Key", key},
		{settingsModel, "Model", model},
		{settingsScan, "Scan", fmt.Sprintf("%s · %s · %d turns · %s", mode, budget, turns, scope)},
	}
}

func (m Model) summaryStep(width int) string {
	rows := m.summaryRows()
	lines := make([]string, 0, len(rows))
	for index, row := range rows {
		marker := "  "
		labelStyle := render.Dim()
		if index == m.settings.summaryCursor && !m.settings.readOnly {
			marker = render.Col(green).Render("▸ ")
			labelStyle = render.Col(white)
		}
		line := marker + labelStyle.Render(row.label) + render.Dim().Render("  ") + render.Col(textColor).Render(row.value)
		lines = append(lines, truncate(line, width))
	}
	return strings.Join(lines, "\n")
}

func (m Model) providerStep(width int) string {
	if len(m.settings.providers) == 0 {
		if m.settings.modelsError != "" {
			return truncate(render.Col(amber).Render(m.settings.modelsError), width)
		}
		return render.Dim().Render("Loading providers…")
	}
	list := m.filteredProviders()
	if len(list) == 0 {
		return render.Dim().Render("No providers match " + m.settings.providerFilter)
	}
	return m.settingsFilterLine(m.settings.providerFilter, width) + m.renderChoices(width, len(list), m.settings.providerCursor, func(index int) string {
		return list[index].Label
	})
}

func (m Model) keyStep(width int) string {
	if m.settings.providerID == "chatgpt" {
		lines := []string{render.Col(white).Render("Sign in with ChatGPT")}
		if m.snapshot.ChatGPTSignedIn {
			lines = append(lines, render.Dim().Render("Already signed in. Enter continues."))
		}
		if m.settings.authURL != "" {
			lines = append(lines, truncate(render.Dim().Render(m.settings.authURL), width))
		}
		if m.settings.authWaiting {
			lines = append(lines, render.Dim().Render("Waiting for the browser…"))
		}
		lines = append(lines, m.fieldLine("Redirect", m.settings.pasteInput.View(), m.settings.editing == "paste", width))
		if m.settings.authError != "" {
			lines = append(lines, truncate(render.Col(amber).Render(m.settings.authError), width))
		}
		return strings.Join(lines, "\n")
	}
	keyValue := "not set"
	if strings.TrimSpace(m.settings.keyInput.Value()) != "" {
		keyValue = m.settings.keyInput.View()
	} else if m.snapshot.KeyConfigured {
		keyValue = m.snapshot.KeyHint
	}
	if m.settings.editing == "key" {
		keyValue = m.settings.keyInput.View()
	}
	lines := []string{m.choiceLine(m.settings.keyCursor == 0, "API key", keyValue, width)}
	if m.providerNeedsBase() {
		base := strings.TrimSpace(m.settings.baseInput.Value())
		if base == "" {
			base = "optional"
		}
		if m.settings.editing == "base" {
			base = m.settings.baseInput.View()
		}
		lines = append(lines, m.choiceLine(m.settings.keyCursor == 1, "API base", base, width))
	}
	if m.snapshot.ShellLocksConnection {
		lines = append(lines, truncate(render.Col(amber).Render("A shell LAMIA_LLM or LLM_API_KEY wins next launch. This change lasts for this session."), width))
	}
	if note := m.settings.modelsError; note != "" {
		lines = append(lines, truncate(render.Col(amber).Render(note), width))
	}
	return strings.Join(lines, "\n")
}

func (m Model) modelStep(width int) string {
	if m.settings.modelsLoading {
		return render.Dim().Render("Loading models from the provider…")
	}
	lines := []string{}
	if m.settings.modelSource == "catalog" && m.settings.modelNote != "" {
		lines = append(lines, truncate(render.Dim().Render(m.settings.modelNote), width))
	} else if m.settings.modelNote != "" {
		lines = append(lines, truncate(render.Dim().Render(m.settings.modelNote), width))
	}
	if m.settings.modelsError != "" {
		lines = append(lines, truncate(render.Col(amber).Render(m.settings.modelsError), width))
	}
	list := m.filteredModels()
	body := m.settingsFilterLine(m.settings.modelFilter, width)
	body += m.renderChoices(width, m.modelChoiceCount(), m.settings.modelCursor, func(index int) string {
		if index >= len(list) {
			if m.settings.editing == "manual" {
				return "Other  " + m.settings.manualInput.View()
			}
			return "Other model id…"
		}
		label := list[index].ID
		if list[index].Tools != nil && !*list[index].Tools {
			label += "  no tools"
		}
		return label
	})
	if m.settings.modelCursor < len(list) {
		body += "\n" + truncate(render.Dim().Render(m.detailsLine()), width)
	}
	if len(lines) == 0 {
		return body
	}
	return strings.Join(lines, "\n") + "\n" + body
}

func (m Model) scanStep(width int) string {
	rows := m.scanRows()
	lines := make([]string, 0, len(rows)+2)
	for index, row := range rows {
		label, value := m.scanRowText(row)
		lines = append(lines, m.choiceLine(index == m.settings.scanCursor, label, value, width))
	}
	if hint := scanModeHint(m.settings.draft.mode); m.scanRows()[min(m.settings.scanCursor, len(rows)-1)] == "mode" {
		lines = append(lines, truncate(render.Dim().Render(hint), width))
	}
	if m.settings.modelsError != "" {
		lines = append(lines, truncate(render.Col(amber).Render(m.settings.modelsError), width))
	}
	return strings.Join(lines, "\n")
}

func (m Model) scanRowText(row string) (string, string) {
	switch row {
	case "mode":
		return "Scan", m.settings.draft.mode
	case "budget":
		if strings.TrimSpace(m.settings.draft.budget) == "" {
			return "Budget", "no cap"
		}
		return "Budget", "$" + m.settings.draft.budget
	case "turns":
		return "Turns", m.settings.draft.turns
	case "scope":
		return "Scope", m.settings.draft.scope
	case "diff":
		value := m.settings.draft.diffBase
		if value == "" {
			value = "default branch"
		}
		if m.settings.editing == "diff" {
			value = m.settings.diffInput.View()
		}
		return "Diff base", value
	case "reasoning":
		return "Reasoning", m.settings.draft.reasoning
	default:
		return row, ""
	}
}

func (m Model) scanRows() []string {
	rows := []string{"mode", "budget", "turns", "scope"}
	if m.settings.draft.scope == "diff" {
		rows = append(rows, "diff")
	}
	if m.settings.draft.showReasoning || m.snapshot.SupportsReasoning {
		rows = append(rows, "reasoning")
	}
	return rows
}

func (m Model) settingsFooter() string {
	if m.settings.readOnly {
		return "esc close"
	}
	if m.settings.editing != "" {
		return "enter confirm    esc cancel"
	}
	switch m.settings.step {
	case settingsScan:
		return "↑/↓ row    ←/→ change    enter edit    esc back"
	case settingsProvider, settingsModel:
		return "↑/↓ move    type to filter    enter select    esc back"
	default:
		return "↑/↓ move    enter select    esc back"
	}
}

func (m Model) settingsFilterLine(filter string, width int) string {
	if filter == "" {
		return ""
	}
	return truncate(render.Dim().Render("/"+filter), width) + "\n"
}

func (m Model) renderChoices(width, count, cursor int, label func(int) string) string {
	if count == 0 {
		return render.Dim().Render("Nothing to show")
	}
	window := m.settingsListRows()
	start := 0
	if cursor >= window {
		start = cursor - window + 1
	}
	end := min(count, start+window)
	lines := make([]string, 0, end-start)
	for index := start; index < end; index++ {
		lines = append(lines, m.choiceLine(index == cursor, "", label(index), width))
	}
	return strings.Join(lines, "\n")
}

func (m Model) choiceLine(selected bool, label, value string, width int) string {
	marker := "  "
	if selected && !m.settings.readOnly {
		marker = render.Col(green).Render("▸ ")
	}
	text := value
	if label != "" {
		text = label + "  " + value
	}
	style := render.Col(textColor)
	if selected && !m.settings.readOnly {
		style = render.Col(white)
	}
	return truncate(marker+style.Render(text), width)
}

func (m Model) fieldLine(label, value string, selected bool, width int) string {
	return m.choiceLine(selected, label, value, width)
}

func (m Model) settingsListRows() int {
	if m.height > 0 && m.height < 22 {
		return 4
	}
	if m.height > 0 && m.height < 30 {
		return 6
	}
	return 8
}

func (m Model) filteredProviders() []providerOption {
	filter := strings.ToLower(strings.TrimSpace(m.settings.providerFilter))
	if filter == "" {
		return m.settings.providers
	}
	matched := make([]providerOption, 0)
	for _, provider := range m.settings.providers {
		if strings.Contains(strings.ToLower(provider.Label), filter) || strings.Contains(strings.ToLower(provider.ID), filter) {
			matched = append(matched, provider)
		}
	}
	return matched
}

func (m Model) filteredModels() []modelOption {
	filter := strings.ToLower(strings.TrimSpace(m.settings.modelFilter))
	if filter == "" {
		return m.settings.models
	}
	matched := make([]modelOption, 0)
	for _, model := range m.settings.models {
		if strings.Contains(strings.ToLower(model.ID), filter) {
			matched = append(matched, model)
		}
	}
	return matched
}

func (m Model) modelChoiceCount() int {
	return len(m.filteredModels()) + 1
}

func (m Model) providerNeedsBase() bool {
	for _, provider := range m.settings.providers {
		if provider.ID == m.settings.providerID {
			return provider.NeedsBase
		}
	}
	return m.settings.providerID == "ollama" || m.settings.providerID == "custom" || m.settings.providerID == "ollama_chat"
}

func (m Model) providerNeedsKey() bool {
	for _, provider := range m.settings.providers {
		if provider.ID == m.settings.providerID {
			return provider.NeedsKey
		}
	}
	return m.settings.providerID != "ollama" && m.settings.providerID != "chatgpt"
}

func (m *Model) appendSettingsFilter(text string) bool {
	if m.settings.step != settingsProvider && m.settings.step != settingsModel {
		return false
	}
	if len(text) != 1 || text[0] < 32 {
		return false
	}
	if m.settings.step == settingsProvider {
		m.settings.providerFilter += text
		m.settings.providerCursor = 0
		return true
	}
	m.settings.modelFilter += text
	m.settings.modelCursor = 0
	return true
}

func (m *Model) trimSettingsFilter() {
	switch m.settings.step {
	case settingsProvider:
		if m.settings.providerFilter != "" {
			m.settings.providerFilter = m.settings.providerFilter[:len(m.settings.providerFilter)-1]
			m.settings.providerCursor = 0
		}
	case settingsModel:
		if m.settings.modelFilter != "" {
			m.settings.modelFilter = m.settings.modelFilter[:len(m.settings.modelFilter)-1]
			m.settings.modelCursor = 0
		}
	}
}

func (m Model) detailsLine() string {
	info := m.settings.details
	parts := []string{}
	if info.MaxInput > 0 {
		parts = append(parts, formatTokens(info.MaxInput)+" in")
	}
	if info.MaxOutput > 0 {
		parts = append(parts, formatTokens(info.MaxOutput)+" out")
	}
	if info.InputCost != nil || info.OutputCost != nil {
		in, out := "?", "?"
		if info.InputCost != nil {
			in = formatPrice(*info.InputCost)
		}
		if info.OutputCost != nil {
			out = formatPrice(*info.OutputCost)
		}
		parts = append(parts, in+" / "+out+" per 1M")
	}
	if info.SupportsTools != nil && !*info.SupportsTools {
		parts = append(parts, "no tools")
	} else if info.SupportsTools != nil {
		parts = append(parts, "tools")
	}
	if len(parts) == 0 {
		return "LiteLLM has no extra detail for this model"
	}
	return strings.Join(parts, " · ")
}

func defaultModelCursor(models []modelOption) int {
	for index, model := range models {
		if model.Tools == nil || *model.Tools {
			return index
		}
	}
	return 0
}

func providerIDFromModel(model string) string {
	model = strings.TrimSpace(model)
	if strings.HasPrefix(model, "chatgpt/") {
		return "chatgpt"
	}
	if slash := strings.Index(model, "/"); slash > 0 {
		return model[:slash]
	}
	return ""
}

func providerLabelFromModel(model string) string {
	id := providerIDFromModel(model)
	if id == "" {
		return "not set"
	}
	if id == "chatgpt" {
		return "ChatGPT subscription"
	}
	return id
}

var scanModeOrder = []string{"quick", "standard", "deep", "exhaustive"}

func scanModeHint(mode string) string {
	switch mode {
	case "quick":
		return "Fast pass. High-impact issues only."
	case "standard":
		return "Routine review of the attack surface."
	case "exhaustive":
		return "Every applicable class, with scanner escalation."
	default:
		return "Thorough. Close each path before the next."
	}
}

func cycleString(values []string, current string, delta int) string {
	if len(values) == 0 {
		return current
	}
	index := 0
	for i, value := range values {
		if value == current {
			index = i
			break
		}
	}
	return values[clampCycle(index+delta, len(values))]
}

func formatTokens(count int) string {
	if count >= 1_000_000 {
		return fmt.Sprintf("%.1fM", float64(count)/1_000_000)
	}
	if count >= 1000 {
		return fmt.Sprintf("%dk", count/1000)
	}
	return strconv.Itoa(count)
}

func formatPrice(amount float64) string {
	return fmt.Sprintf("$%.2f", amount)
}
