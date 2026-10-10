<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\ManagementHistoryReportExporter;
use App\Services\Reports\ManagementHistoryReportPeriod;
use Carbon\CarbonImmutable;
use OpenSpout\Reader\XLSX\Reader;
use Tests\TestCase;
use ZipArchive;

class ManagementHistoryReportExporterTest extends TestCase
{
    public function test_writes_streamed_xlsx_with_exact_headers_types_and_formatting(): void
    {
        $temporaryRoot = sys_get_temp_dir().DIRECTORY_SEPARATOR.'kpdm-report-export-'.bin2hex(random_bytes(8));
        config([
            'reports.management_history.temporary_directory' => $temporaryRoot,
            'reports.management_history.filename_prefix' => 'historico_gestiones',
            'reports.management_history.timezone' => 'America/Lima',
            'reports.management_history.source_timezone' => 'UTC',
        ]);
        $period = ManagementHistoryReportPeriod::forExecution(
            CarbonImmutable::parse('2026-10-09 10:00:00', 'America/Lima'),
        );
        $exporter = new ManagementHistoryReportExporter;
        $rows = (function (): iterable {
            yield [
                'fecha_hora' => CarbonImmutable::parse('2026-10-02 10:28:00', 'America/Lima'),
                'cliente' => 'Cliente de prueba',
                'documento' => '00001234',
                'telefono' => '934043966',
                'agente' => 'Agente Uno',
                'canal' => 'LLAMADA',
                'tipificacion_n1' => 'CONTACTO',
                'tipificacion_n2' => 'YA_PAGO',
                'tipificacion_n3' => 'VALIDADO',
                'resultado' => 'GESTIONADO',
                'duracion' => 45,
                'promesa' => 'Si',
                'monto' => 150.75,
                'notas' => 'Nota sintética',
                'peso' => 1,
            ];
        })();

        $export = $exporter->export($rows, $period);

        try {
            $this->assertSame('historico_gestiones_20261008.xlsx', $export->filename);
            $this->assertSame(1, $export->recordCount);
            $this->assertFileExists($export->path);

            [$sheetName, $header, $data] = $this->readWorkbook($export->path);
            $this->assertSame('Gestiones', $sheetName);
            $this->assertSame(ManagementHistoryReportExporter::HEADERS, $header);
            $this->assertCount(15, $header);
            $this->assertSame('00001234', $data[2]);
            $this->assertSame('934043966', $data[3]);
            $this->assertSame(45, $data[10]);
            $this->assertSame(150.75, $data[12]);
            $this->assertSame(1, $data[14]);

            $sheetXml = $this->zipEntry($export->path, 'xl/worksheets/sheet1.xml');
            $stylesXml = $this->zipEntry($export->path, 'xl/styles.xml');
            $this->assertStringContainsString('<autoFilter ref="A1:O2"', $sheetXml);
            $this->assertStringContainsString('ySplit="1"', $sheetXml);
            $this->assertMatchesRegularExpression('/<c r="C2"[^>]*t="inlineStr"/', $sheetXml);
            $this->assertMatchesRegularExpression('/<c r="D2"[^>]*t="inlineStr"/', $sheetXml);
            $this->assertStringContainsString('Aptos Narrow', $stylesXml);
            $this->assertStringContainsString('<sz val="11"', $stylesXml);
            $this->assertStringContainsString('rgb="3366FF"', $stylesXml);
            $this->assertStringContainsString('rgb="FFFFFFFF"', $stylesXml);
        } finally {
            $exporter->delete($export);
            @rmdir($temporaryRoot);
        }
    }

    /** @return array{string, list<mixed>, list<mixed>} */
    private function readWorkbook(string $path): array
    {
        $reader = new Reader;
        $reader->open($path);

        try {
            foreach ($reader->getSheetIterator() as $sheet) {
                $rows = [];

                foreach ($sheet->getRowIterator() as $row) {
                    $rows[] = $row->toArray();
                }

                return [$sheet->getName(), $rows[0], $rows[1]];
            }
        } finally {
            $reader->close();
        }

        $this->fail('El XLSX no contiene una hoja.');
    }

    private function zipEntry(string $path, string $entry): string
    {
        $zip = new ZipArchive;
        $this->assertTrue($zip->open($path) === true);

        try {
            $contents = $zip->getFromName($entry);
            $this->assertIsString($contents);

            return $contents;
        } finally {
            $zip->close();
        }
    }
}
