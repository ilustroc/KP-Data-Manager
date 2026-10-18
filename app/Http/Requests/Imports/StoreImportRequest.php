<?php

namespace App\Http\Requests\Imports;

use App\FinancialEntity;
use App\ImportOrigin;
use App\ImportType;
use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

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
            'tipo' => [
                'required',
                Rule::enum(ImportType::class),
                Rule::in(config('imports.registration_types', [])),
            ],
            'entidad' => ['nullable', Rule::enum(FinancialEntity::class)],
            'origen' => ['required', Rule::enum(ImportOrigin::class)],
            'archivo' => ['required', 'file', "extensions:{$extensions}", "max:{$maximumKilobytes}"],
        ];
    }

    /**
     * @return array<callable(Validator): void>
     */
    public function after(): array
    {
        return [
            function (Validator $validator): void {
                if ($validator->errors()->hasAny(['tipo', 'entidad'])) {
                    return;
                }

                $isPortfolio = $this->input('tipo') === ImportType::Portfolio->value;
                $entity = FinancialEntity::tryFrom((string) $this->input('entidad'));

                if ($isPortfolio && $entity === null) {
                    $validator->errors()->add('entidad', 'Selecciona la entidad financiera de la cartera.');

                    return;
                }

                if ($isPortfolio && ! $entity->isImplemented()) {
                    $validator->errors()->add('entidad', 'La entidad seleccionada aún no está disponible para procesamiento.');
                }

                if (! $isPortfolio && $this->filled('entidad')) {
                    $validator->errors()->add('entidad', 'La entidad financiera solo corresponde a cargas de cartera.');
                }
            },
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
            'tipo.in' => 'Este tipo de carga todavía no está habilitado en el flujo de registro.',
            'entidad.enum' => 'La entidad financiera seleccionada no es válida.',
            'origen.required' => 'Selecciona el origen de la carga.',
            'origen.enum' => 'El origen seleccionado no es válido.',
            'archivo.required' => 'Selecciona un archivo para registrar.',
            'archivo.file' => 'El archivo enviado no es válido.',
            'archivo.extensions' => 'Solo se permiten archivos CSV o XLSX.',
            'archivo.max' => 'El archivo excede el límite permitido para cargas web.',
        ];
    }
}
