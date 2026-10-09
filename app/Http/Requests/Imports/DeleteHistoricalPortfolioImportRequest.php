<?php

namespace App\Http\Requests\Imports;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class DeleteHistoricalPortfolioImportRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->can('administer') ?? false;
    }

    /**
     * @return array<string, array<mixed>>
     */
    public function rules(): array
    {
        return [
            'confirmation' => ['required', 'string', Rule::in(['ELIMINAR'])],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'confirmation.required' => 'Escribe ELIMINAR para confirmar la operación.',
            'confirmation.in' => 'La confirmación debe coincidir exactamente con ELIMINAR.',
        ];
    }
}
