<?php

namespace Tests\Feature\Imports;

use App\Models\User;
use Illuminate\Support\Facades\Storage;

class ImportFileControllerTest extends ImportFeatureTestCase
{
    public function test_download_requires_operator_authorization(): void
    {
        Storage::fake('imports');
        $batchId = $this->createBatch();
        Storage::disk('imports')->put('2026/10/1/internal.csv', 'private contents');

        $this->get(route('imports.file', $batchId))->assertRedirectToRoute('login');

        $reader = User::factory()->readOnly()->create();
        $this->actingAs($reader)->get(route('imports.file', $batchId))->assertForbidden();
    }

    public function test_operator_can_download_original_through_streamed_response(): void
    {
        Storage::fake('imports');
        $batchId = $this->createBatch(['archivo_original' => 'pagos privados.csv']);
        Storage::disk('imports')->put('2026/10/1/internal.csv', 'private contents');
        $operator = User::factory()->operator()->create();

        $response = $this->actingAs($operator)->get(route('imports.file', $batchId));

        $response
            ->assertOk()
            ->assertDownload('pagos privados.csv');
        $this->assertSame('private contents', $response->streamedContent());
        $this->assertSame('nosniff', $response->headers->get('X-Content-Type-Options'));
    }

    public function test_missing_private_file_returns_404(): void
    {
        Storage::fake('imports');
        $batchId = $this->createBatch();
        $operator = User::factory()->operator()->create();

        $this->actingAs($operator)->get(route('imports.file', $batchId))->assertNotFound();
    }
}
