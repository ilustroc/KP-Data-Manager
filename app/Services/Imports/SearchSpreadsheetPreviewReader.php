<?php

namespace App\Services\Imports;

use Closure;
use DateTimeInterface;
use OpenSpout\Reader\CSV\Options as CsvOptions;
use OpenSpout\Reader\CSV\Reader as CsvReader;
use OpenSpout\Reader\ReaderInterface;
use OpenSpout\Reader\XLSX\Reader as XlsxReader;
use Throwable;

final class SearchSpreadsheetPreviewReader
{
    /**
     * @param  null|Closure(int, list<string>, list<string|null>): void  $inspectRow
     * @return array{headers: list<string>, rows: list<list<string|null>>, total_rows: int, empty_rows: int}
     */
    public function read(
        string $path,
        string $extension,
        int $limit = 20,
        ?Closure $inspectRow = null,
    ): array {
        $reader = $this->reader($path, $extension);

        try {
            $reader->open($path);
            $sheet = $reader->getSheetIterator()->current();
            if ($sheet === null) {
                throw new InvalidImportFile('El archivo no contiene hojas o datos legibles.');
            }

            $headers = [];
            $rows = [];
            $totalRows = 0;
            $emptyRows = 0;
            foreach ($sheet->getRowIterator() as $index => $row) {
                $values = array_map($this->render(...), $row->toArray());
                if ($index === 1) {
                    $headers = $this->headers($values);

                    continue;
                }
                if ($this->isEmpty($values)) {
                    $emptyRows++;

                    continue;
                }
                $values = array_pad(array_slice($values, 0, count($headers)), count($headers), null);
                $totalRows++;
                if (count($rows) < $limit) {
                    $rows[] = $values;
                }
                $inspectRow?->__invoke($index, $headers, $values);
            }

            if ($headers === []) {
                throw new InvalidImportFile('El archivo no contiene encabezados.');
            }

            return [
                'headers' => $headers,
                'rows' => $rows,
                'total_rows' => $totalRows,
                'empty_rows' => $emptyRows,
            ];
        } catch (InvalidImportFile $exception) {
            throw $exception;
        } catch (Throwable $exception) {
            throw new InvalidImportFile('No fue posible leer el archivo para generar el preview.', previous: $exception);
        } finally {
            $reader->close();
        }
    }

    private function reader(string $path, string $extension): ReaderInterface
    {
        if ($extension === 'xlsx') {
            return new XlsxReader;
        }
        if ($extension !== 'csv') {
            throw new InvalidImportFile('El formato no está disponible para preview SEARCH.');
        }

        $options = new CsvOptions;
        $sample = file_get_contents($path, false, null, 0, 32768);
        $options->FIELD_DELIMITER = substr_count((string) $sample, ';') > substr_count((string) $sample, ',') ? ';' : ',';

        return new CsvReader($options);
    }

    /**
     * @param  list<string|null>  $values
     * @return list<string>
     */
    private function headers(array $values): array
    {
        $headers = array_map(static fn (?string $value): string => trim((string) $value), $values);
        while ($headers !== [] && end($headers) === '') {
            array_pop($headers);
        }
        if (in_array('', $headers, true)) {
            throw new InvalidImportFile('Todos los encabezados detectados deben tener nombre.');
        }
        if (count(array_unique($headers)) !== count($headers)) {
            throw new InvalidImportFile('El archivo contiene encabezados duplicados.');
        }

        return $headers;
    }

    private function render(mixed $value): ?string
    {
        if ($value === null || $value === '') {
            return null;
        }
        if ($value instanceof DateTimeInterface) {
            return $value->format('Y-m-d');
        }
        if (is_bool($value)) {
            return $value ? 'TRUE' : 'FALSE';
        }
        if (is_float($value) && floor($value) === $value) {
            return number_format($value, 0, '.', '');
        }

        return trim((string) $value);
    }

    /** @param list<string|null> $values */
    private function isEmpty(array $values): bool
    {
        foreach ($values as $value) {
            if ($value !== null && trim($value) !== '') {
                return false;
            }
        }

        return true;
    }
}
