<?php

namespace App\Services\Reports;

use OpenSpout\Common\Entity\Row;
use OpenSpout\Common\Entity\Style\Color;
use OpenSpout\Common\Entity\Style\Style;
use OpenSpout\Writer\AutoFilter;
use OpenSpout\Writer\XLSX\Entity\SheetView;
use OpenSpout\Writer\XLSX\Options;
use OpenSpout\Writer\XLSX\Writer;
use RuntimeException;
use Throwable;

class ManagementHistoryReportExporter
{
    public const HEADERS = [
        'Fecha/Hora',
        'Cliente',
        'Documento',
        'Teléfono',
        'Agente',
        'Canal',
        'Tip. L1',
        'Tip. L2',
        'Tip. L3',
        'Resultado',
        'Duración',
        'Promesa',
        'Monto',
        'Notas',
        'Peso',
    ];

    private const COLUMN_WIDTHS = [18, 35, 15, 15, 25, 15, 30, 30, 35, 20, 12, 10, 15, 60, 8];

    /**
     * @param  iterable<array<string, mixed>>  $rows
     */
    public function export(iterable $rows, ManagementHistoryReportPeriod $period): ManagementHistoryExport
    {
        $rootDirectory = (string) config(
            'reports.management_history.temporary_directory',
            storage_path('app/private/reports'),
        );
        $runDirectory = $rootDirectory.DIRECTORY_SEPARATOR.bin2hex(random_bytes(16));
        $filenamePrefix = (string) config(
            'reports.management_history.filename_prefix',
            'historico_gestiones',
        );
        $filename = $filenamePrefix.'_'.$period->filenameDate().'.xlsx';
        $path = $runDirectory.DIRECTORY_SEPARATOR.$filename;

        $this->createDirectory($runDirectory);

        $writer = $this->writer($runDirectory);
        $isOpen = false;

        try {
            $writer->openToFile($path);
            $isOpen = true;

            $sheet = $writer->getCurrentSheet();
            $sheet->setName('Gestiones');
            $sheet->setSheetView((new SheetView)->setFreezeRow(2));

            foreach (self::COLUMN_WIDTHS as $index => $width) {
                $sheet->setColumnWidth($width, $index + 1);
            }

            $writer->addRow(Row::fromValues(self::HEADERS, $this->headerStyle()));

            $recordCount = 0;
            $columnStyles = $this->columnStyles();

            foreach ($rows as $row) {
                $writer->addRow(Row::fromValuesWithStyles(
                    $this->rowValues($row),
                    columnStyles: $columnStyles,
                ));
                $recordCount++;
            }

            $sheet->setAutoFilter(new AutoFilter(0, 1, 14, max(1, $recordCount + 1)));
            $writer->close();
            $isOpen = false;

            return new ManagementHistoryExport($path, $filename, $recordCount);
        } catch (Throwable $exception) {
            if ($isOpen) {
                try {
                    $writer->close();
                } catch (Throwable) {
                    // Preserve the original export exception.
                }
            }

            $this->deletePath($path);
            $this->deleteEmptyDirectory($runDirectory);

            throw $exception;
        }
    }

    public function delete(ManagementHistoryExport $export): void
    {
        $this->deletePath($export->path);
        $this->deleteEmptyDirectory(dirname($export->path));
    }

    private function writer(string $tempFolder): Writer
    {
        $options = new Options;
        $options->DEFAULT_ROW_STYLE = (new Style)
            ->setFontName('Aptos Narrow')
            ->setFontSize(11)
            ->setFontColor(Color::BLACK);
        $options->setTempFolder($tempFolder);

        return new Writer($options);
    }

    private function headerStyle(): Style
    {
        return (new Style)
            ->setFontName('Aptos Narrow')
            ->setFontSize(11)
            ->setFontColor(Color::WHITE)
            ->setFontBold()
            ->setBackgroundColor('3366FF');
    }

    /**
     * @return array<int, Style>
     */
    private function columnStyles(): array
    {
        return [
            0 => (new Style)->setFormat('d/m/yyyy hh:mm'),
            2 => (new Style)->setFormat('@'),
            3 => (new Style)->setFormat('@'),
            12 => (new Style)->setFormat('#,##0.00'),
        ];
    }

    /**
     * @param  array<string, mixed>  $row
     * @return list<mixed>
     */
    private function rowValues(array $row): array
    {
        return [
            $row['fecha_hora'],
            $row['cliente'],
            $row['documento'],
            $row['telefono'],
            $row['agente'],
            $row['canal'],
            $row['tipificacion_n1'],
            $row['tipificacion_n2'],
            $row['tipificacion_n3'],
            $row['resultado'],
            $row['duracion'],
            $row['promesa'],
            $row['monto'],
            $row['notas'],
            $row['peso'],
        ];
    }

    private function createDirectory(string $directory): void
    {
        if (! is_dir($directory) && ! mkdir($directory, 0750, true) && ! is_dir($directory)) {
            throw new RuntimeException('No fue posible crear el directorio temporal del reporte.');
        }
    }

    private function deletePath(string $path): void
    {
        if (is_file($path)) {
            @unlink($path);
        }
    }

    private function deleteEmptyDirectory(string $directory): void
    {
        if (is_dir($directory) && (scandir($directory) ?: []) === ['.', '..']) {
            @rmdir($directory);
        }
    }
}
