{{/*
Expand the name of the chart.
*/}}
{{- define "contributr.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name (release-chart, truncated to 63 chars).
*/}}
{{- define "contributr.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label value.
*/}}
{{- define "contributr.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "contributr.labels" -}}
helm.sh/chart: {{ include "contributr.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/part-of: contributr
{{- end }}

{{/*
Per-component labels. Call with (dict "root" . "component" "backend").
*/}}
{{- define "contributr.componentLabels" -}}
{{ include "contributr.labels" .root }}
app.kubernetes.io/name: {{ .component }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Per-component selector labels.
*/}}
{{- define "contributr.selectorLabels" -}}
app.kubernetes.io/name: {{ .component }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/*
Resolve image reference. Uses per-component .registry when set,
falls back to global.imageRegistry, then plain repository:tag.
*/}}
{{- define "contributr.image" -}}
{{- $reg := .registry | default .root.Values.global.imageRegistry | default "" -}}
{{- if $reg -}}
{{- printf "%s/%s:%s" $reg .repository .tag -}}
{{- else -}}
{{- printf "%s:%s" .repository .tag -}}
{{- end -}}
{{- end }}
