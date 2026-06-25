/**
 * Parse version numbers from artifact file listings.
 * Supports both pipeline-generated files (v1.md, v2.md) and user-uploaded files (any .md/.txt/.pdf).
 */

import type { ArtifactFileListResponse, VersionEntry } from './types';

const VERSION_RE = /v(\d+)\.md$/;
const DOC_EXTENSIONS = /\.(md|txt|pdf)$/i;
// Files to skip (manifests, JSON metadata, briefs)
const SKIP_PATTERNS = /(_manifest\.json|\.json$|brief\.json$)/;

/**
 * Extract sorted version entries for a specific sub-path prefix.
 * Includes both versioned files (v1.md, v2.md) and user-uploaded files.
 */
export function extractVersions(
  fileList: ArtifactFileListResponse,
  subPathPrefix: string,
  currentVersion: number,
): VersionEntry[] {
  const versioned: VersionEntry[] = [];
  const uploads: VersionEntry[] = [];

  for (const file of fileList.files) {
    if (!file.name.startsWith(subPathPrefix)) continue;
    if (SKIP_PATTERNS.test(file.name)) continue;

    const versionMatch = file.name.match(VERSION_RE);
    if (versionMatch) {
      const v = parseInt(versionMatch[1], 10);
      versioned.push({
        version: v,
        label: `v${v}`,
        current: v === currentVersion,
        filePath: file.name,
      });
    } else if (DOC_EXTENSIONS.test(file.name)) {
      // User-uploaded file — show by filename
      const filename = file.name.slice(subPathPrefix.length);
      if (filename && !filename.includes('/')) {
        uploads.push({
          version: -1,
          label: filename,
          current: false,
          filePath: file.name,
          isUpload: true,
        });
      }
    }
  }

  // Sort versioned descending (newest first), then uploads alphabetically
  versioned.sort((a, b) => b.version - a.version);
  uploads.sort((a, b) => a.label.localeCompare(b.label));

  return [...versioned, ...uploads];
}

/**
 * Extract versions for the voice style guide (guide/v{N}.md + uploaded files).
 */
export function extractGuideVersions(
  fileList: ArtifactFileListResponse,
  currentVersion: number,
): VersionEntry[] {
  return extractVersions(fileList, 'guide/', currentVersion);
}

/**
 * Extract versions for a persona (e.g., "marcus/v{N}.md" + uploaded files).
 */
export function extractPersonaVersions(
  fileList: ArtifactFileListResponse,
  personaId: string,
  currentVersion: number,
): VersionEntry[] {
  return extractVersions(fileList, `${personaId}/`, currentVersion);
}
