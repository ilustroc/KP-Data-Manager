<?php

namespace Tests\Feature\Imports;

use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use App\Jobs\ProcessImportBatch;
use App\Models\User;
use App\Services\Imports\ImportFileService;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;
use RuntimeException;

class ImportUploadServiceTest extends ImportFeatureTestCase
{
    public function test_filesystem_failure_marks_created_batch_as_error(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        $this->partialMock(ImportFileService::class, function ($mock): void {
            $mock->shouldReceive('storeFromPath')
                ->once()
                ->andThrow(new RuntimeException('simulated storage failure'));
        });
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Payments->value,
                'origen' => ImportOrigin::Daily->value,
                'archivo' => $this->validCsv(),
            ])
            ->assertInvalid('archivo');

        $batch = DB::connection('sqlite')->table('import_batch')->firstOrFail();
        $this->assertSame(ImportStatus::Error->value, $batch->estado);
        $this->assertNotNull($batch->mensaje_error);
        $this->assertSame([], Storage::disk('imports')->allFiles());
        Queue::assertNothingPushed();
    }

    public function test_database_failure_after_storage_does_not_leave_orphan_file(): void
    {
        Queue::fake([ProcessImportBatch::class]);
        Storage::fake('imports');
        DB::connection('sqlite')->unprepared(<<<'SQL'
            CREATE TRIGGER fail_pending_import
            BEFORE UPDATE ON import_batch
            WHEN NEW.estado = 'PENDIENTE'
            BEGIN
                SELECT RAISE(ABORT, 'simulated database failure');
            END
            SQL);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Payments->value,
                'origen' => ImportOrigin::Daily->value,
                'archivo' => $this->validCsv(),
            ])
            ->assertInvalid('archivo');

        $batch = DB::connection('sqlite')->table('import_batch')->firstOrFail();
        $this->assertSame(ImportStatus::Error->value, $batch->estado);
        $this->assertSame([], Storage::disk('imports')->allFiles());
        Queue::assertNothingPushed();
    }

    public function test_hashing_and_private_storage_use_stream_resources(): void
    {
        Storage::fake('imports');
        $service = app(ImportFileService::class);
        $hashStream = fopen('php://temp', 'w+b');
        $this->assertIsResource($hashStream);
        fwrite($hashStream, 'streamed-data');
        rewind($hashStream);

        $this->assertSame(
            hash('sha256', 'streamed-data'),
            $service->hashStream($hashStream),
        );

        fclose($hashStream);

        $source = tmpfile();
        $this->assertIsResource($source);
        $sourcePath = stream_get_meta_data($source)['uri'];
        $chunk = str_repeat('x', 4096);

        for ($index = 0; $index < 1024; $index++) {
            fwrite($source, $chunk);
        }

        fflush($source);
        $service->storeFromPath($sourcePath, 'large/streamed.csv');

        Storage::disk('imports')->assertExists('large/streamed.csv');
        $this->assertSame(4 * 1024 * 1024, Storage::disk('imports')->size('large/streamed.csv'));

        fclose($source);
    }
}
