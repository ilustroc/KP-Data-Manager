<?php

namespace Tests\Feature\Services\Audit;

use App\Models\User;
use App\Services\Audit\AuditActorResolver;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class AuditActorResolverTest extends TestCase
{
    use LazilyRefreshDatabase;

    public function test_resolves_page_actors_with_one_users_query(): void
    {
        $firstUser = User::factory()->create(['name' => 'Jesús Gabriel Garcia Palacios']);
        $secondUser = User::factory()->create(['name' => 'María Operadora']);
        $records = [
            (object) ['usuario' => 'user:'.$firstUser->id],
            (object) ['usuario' => 'user:'.$secondUser->id],
            (object) ['usuario' => 'user:'.$firstUser->id],
            (object) ['usuario' => 'cli:PC'],
            (object) ['usuario' => 'user:999999'],
        ];
        DB::connection()->flushQueryLog();
        DB::connection()->enableQueryLog();

        app(AuditActorResolver::class)->attachDisplayNames($records);

        $userQueries = collect(DB::connection()->getQueryLog())
            ->filter(static fn (array $query): bool => str_contains($query['query'], 'from "users"'));

        $this->assertSame('Jesús Gabriel Garcia Palacios', $records[0]->usuario_nombre);
        $this->assertSame('María Operadora', $records[1]->usuario_nombre);
        $this->assertSame('Jesús Gabriel Garcia Palacios', $records[2]->usuario_nombre);
        $this->assertSame('Sistema', $records[3]->usuario_nombre);
        $this->assertSame('Usuario no disponible', $records[4]->usuario_nombre);
        $this->assertCount(1, $userQueries);
    }
}
