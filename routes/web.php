<?php

use App\Http\Controllers\Auth\AuthenticatedSessionController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PaymentController;
use App\Http\Controllers\PaymentCorrectionController;
use App\Http\Controllers\PaymentDocumentController;
use App\Http\Controllers\PaymentHistoryController;
use Illuminate\Support\Facades\Route;

Route::redirect('/', '/dashboard');

Route::middleware('guest')->group(function (): void {
    Route::get('/login', [AuthenticatedSessionController::class, 'create'])->name('login');
    Route::post('/login', [AuthenticatedSessionController::class, 'store'])
        ->middleware('throttle:login')
        ->name('login.store');
});

Route::middleware(['auth', 'active'])->group(function (): void {
    Route::get('/dashboard', [DashboardController::class, 'index'])->name('dashboard');
    Route::post('/logout', [AuthenticatedSessionController::class, 'destroy'])->name('logout');

    Route::middleware('can:view-data')->prefix('pagos')->name('payments.')->group(function (): void {
        Route::get('/', [PaymentController::class, 'index'])->name('index');
        Route::get('/sin-identificar', [PaymentController::class, 'unidentified'])->name('unidentified');
        Route::get('/correcciones', PaymentCorrectionController::class)->name('corrections');
        Route::get('/{raw_id}/historial', PaymentHistoryController::class)
            ->whereNumber('raw_id')
            ->name('history');

        Route::middleware('can:operate')->group(function (): void {
            Route::get('/{raw_id}/identificar', [PaymentDocumentController::class, 'createIdentify'])
                ->whereNumber('raw_id')
                ->name('identify.create');
            Route::post('/{raw_id}/identificar', [PaymentDocumentController::class, 'identify'])
                ->whereNumber('raw_id')
                ->name('identify');
            Route::get('/{raw_id}/documento', [PaymentDocumentController::class, 'edit'])
                ->whereNumber('raw_id')
                ->name('edit-document');
            Route::patch('/{raw_id}/documento', [PaymentDocumentController::class, 'update'])
                ->whereNumber('raw_id')
                ->name('update-document');
        });

        Route::get('/{raw_id}', [PaymentController::class, 'show'])
            ->whereNumber('raw_id')
            ->name('show');
    });
});
