<?php

namespace App\Http\Requests\Imports;

use App\ImportOrigin;
use App\ImportType;
use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreImportRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->can('operate') ?? false;
    }

    /**
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        $maximumKilobytes = max(1, (int) config('imports.max_web_upload_mb')) * 1024;
        $extensions = implode(',', config('imports.allowed_extensions'));

        return [
            'tipo' => ['required', Rule::enum(ImportType::class)],
            'origen' => ['required', Rule::enum(ImportOrigin::class)],
            'archivo' => ['required', 'file', "extensions:{$extensions}", "max:{$maximumKilobytes}"],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'tipo.required' => 'Selecciona el tipo de carga.',
            'tipo.enum' => 'El tipo de carga no es válido.',
            'origen.required' => 'Selecciona el origen de la carga.',
            'origen.enum' => 'El origen seleccionado no es válido.',
            'archivo.required' => 'Selecciona un archivo para registrar.',
            'archivo.file' => 'El archivo enviado no es válido.',
            'archivo.extensions' => 'Solo se permiten archivos CSV o XLSX.',
            'archivo.max' => 'El archivo excede el límite permitido para cargas web.',
        ];
    }
}
