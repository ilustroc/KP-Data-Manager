<?php

namespace App\Services\Imports;

final readonly class SearchImportPreview
{
    /**
     * @param  list<string>  $headers
     * @param  list<list<string|null>>  $rows
     * @param  array<string, string>  $suggestedMapping
     */
    public function __construct(
        public string $token,
        public int $userId,
        public string $datasetCode,
        public string $sourceCode,
        public string $refreshMode,
        public string $origin,
        public string $storedPath,
        public ImportFileMetadata $metadata,
        public array $headers,
        public array $rows,
        public array $suggestedMapping,
        public string $expiresAt,
        public ?SearchImportPreviewAnalysis $analysis = null,
    ) {}

    /** @return array<string, mixed> */
    public function toSession(): array
    {
        return [
            'token' => $this->token,
            'user_id' => $this->userId,
            'dataset_code' => $this->datasetCode,
            'source_code' => $this->sourceCode,
            'refresh_mode' => $this->refreshMode,
            'origin' => $this->origin,
            'stored_path' => $this->storedPath,
            'metadata' => [
                'original_name' => $this->metadata->originalName,
                'extension' => $this->metadata->extension,
                'mime_type' => $this->metadata->mimeType,
                'size' => $this->metadata->size,
                'sha256' => $this->metadata->sha256,
            ],
            'headers' => $this->headers,
            'rows' => $this->rows,
            'suggested_mapping' => $this->suggestedMapping,
            'expires_at' => $this->expiresAt,
            'analysis' => $this->analysis?->toArray(),
        ];
    }

    /** @param array<string, mixed> $values */
    public static function fromSession(array $values): self
    {
        $metadata = $values['metadata'];

        return new self(
            token: (string) $values['token'],
            userId: (int) $values['user_id'],
            datasetCode: (string) $values['dataset_code'],
            sourceCode: (string) $values['source_code'],
            refreshMode: (string) $values['refresh_mode'],
            origin: (string) $values['origin'],
            storedPath: (string) $values['stored_path'],
            metadata: new ImportFileMetadata(
                originalName: (string) $metadata['original_name'],
                extension: (string) $metadata['extension'],
                mimeType: (string) $metadata['mime_type'],
                size: (int) $metadata['size'],
                sha256: (string) $metadata['sha256'],
            ),
            headers: array_values($values['headers']),
            rows: array_values($values['rows']),
            suggestedMapping: $values['suggested_mapping'],
            expiresAt: (string) $values['expires_at'],
            analysis: isset($values['analysis']) && is_array($values['analysis'])
                ? SearchImportPreviewAnalysis::fromArray($values['analysis'])
                : null,
        );
    }
}
